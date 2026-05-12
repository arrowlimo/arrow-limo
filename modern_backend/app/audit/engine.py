"""Audit event persistence and automated audit checks."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import date, datetime, timedelta
from typing import Any

from .catalog import AUDIT_EVENT_SCHEMA
from .schemas import (
    AuditCheckFinding,
    AuditCheckReport,
    AuditCheckRequest,
    AuditEvent,
    AuditStatus,
)


def _table_exists(conn, table_name: str) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = %s
            LIMIT 1
            """,
            (table_name,),
        )
        return cur.fetchone() is not None


def _has_column(conn, table_name: str, column_name: str) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = %s
              AND column_name = %s
            LIMIT 1
            """,
            (table_name, column_name),
        )
        return cur.fetchone() is not None


def _first_existing_column(
    conn, table_name: str, candidates: list[str]
) -> str | None:
    for candidate in candidates:
        if _has_column(conn, table_name, candidate):
            return candidate
    return None


def _safe_count(conn, sql: str, params: tuple[Any, ...] = ()) -> int:
    with conn.cursor() as cur:
        cur.execute(sql, params)
        row = cur.fetchone()
        return int(row[0] or 0) if row else 0


def _safe_sum(conn, sql: str, params: tuple[Any, ...] = ()) -> float:
    with conn.cursor() as cur:
        cur.execute(sql, params)
        row = cur.fetchone()
        return float(row[0] or 0.0) if row else 0.0


def ensure_audit_storage(conn) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_events (
                audit_event_pk BIGSERIAL PRIMARY KEY,
                event_id TEXT UNIQUE NOT NULL,
                occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                module TEXT NOT NULL,
                entity_type TEXT NOT NULL,
                entity_id TEXT NOT NULL,
                action TEXT NOT NULL,
                source TEXT NOT NULL,
                correlation_id TEXT,
                actor_json JSONB NOT NULL,
                before_json JSONB,
                after_json JSONB,
                evidence_links JSONB NOT NULL DEFAULT '[]'::jsonb,
                retention_until DATE NOT NULL,
                note TEXT,
                prev_hash TEXT,
                event_hash TEXT,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_package_runs (
                package_run_id BIGSERIAL PRIMARY KEY,
                package_id TEXT UNIQUE NOT NULL,
                package_name TEXT NOT NULL,
                package_mode TEXT NOT NULL,
                fiscal_year INTEGER NOT NULL,
                date_from DATE,
                date_to DATE,
                generated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                generated_by TEXT NOT NULL,
                generated_by_name TEXT,
                correlation_id TEXT,
                retention_policy TEXT NOT NULL DEFAULT '6+ years',
                overall_status TEXT NOT NULL,
                content_hash TEXT NOT NULL,
                zip_path TEXT NOT NULL,
                notes_path TEXT NOT NULL,
                manifest_json JSONB NOT NULL,
                checks_json JSONB NOT NULL,
                status TEXT NOT NULL DEFAULT 'ready'
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_check_runs (
                audit_check_run_id BIGSERIAL PRIMARY KEY,
                run_id TEXT UNIQUE NOT NULL,
                fiscal_year INTEGER NOT NULL,
                generated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                generated_by TEXT NOT NULL,
                correlation_id TEXT,
                overall_status TEXT NOT NULL,
                summary_json JSONB NOT NULL,
                findings_json JSONB NOT NULL
            )
            """
        )
        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_audit_events_occurred_at
            ON audit_events (occurred_at DESC)
            """
        )
        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_audit_events_module_action_time
            ON audit_events (module, action, occurred_at DESC)
            """
        )
        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_audit_events_entity
            ON audit_events (entity_type, entity_id)
            """
        )
        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_audit_events_username
            ON audit_events ((actor_json->>'username'))
            """
        )
        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_audit_events_correlation_id
            ON audit_events (correlation_id)
            WHERE correlation_id IS NOT NULL
            """
        )
        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_audit_package_runs_fiscal_year_generated
            ON audit_package_runs (fiscal_year, generated_at DESC)
            """
        )
        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_audit_check_runs_fiscal_year_generated
            ON audit_check_runs (fiscal_year, generated_at DESC)
            """
        )
        cur.execute(
            """
            CREATE OR REPLACE FUNCTION prevent_audit_event_mutation()
            RETURNS trigger AS $$
            BEGIN
                RAISE EXCEPTION 'audit_events is append-only';
            END;
            $$ LANGUAGE plpgsql;
            """
        )
        cur.execute("DROP TRIGGER IF EXISTS trg_audit_events_immutable ON audit_events")
        cur.execute(
            """
            CREATE TRIGGER trg_audit_events_immutable
            BEFORE UPDATE OR DELETE ON audit_events
            FOR EACH ROW EXECUTE FUNCTION prevent_audit_event_mutation()
            """
        )
    conn.commit()


def record_audit_event(
    conn,
    event: AuditEvent,
    *,
    ensure_storage: bool = True,
    commit: bool = True,
) -> dict[str, Any]:
    if ensure_storage:
        ensure_audit_storage(conn)
    payload = event.model_dump(mode="json")
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    with conn.cursor() as cur:
        cur.execute(
            "SELECT event_hash FROM audit_events ORDER BY audit_event_pk DESC LIMIT 1"
        )
        row = cur.fetchone()
        prev_hash = row[0] if row else None
    event.prev_hash = prev_hash
    event.event_hash = hashlib.sha256(
        ((prev_hash or "") + canonical).encode("utf-8")
    ).hexdigest()
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO audit_events (
                event_id, occurred_at, module, entity_type, entity_id,
                action, source, correlation_id, actor_json, before_json,
                after_json, evidence_links, retention_until, note, prev_hash,
                event_hash
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb,
                %s::jsonb, %s::jsonb, %s, %s, %s, %s
            )
            """,
            (
                event.event_id,
                event.occurred_at,
                event.module,
                event.entity_type,
                event.entity_id,
                event.action,
                event.source,
                event.correlation_id,
                json.dumps(event.actor.model_dump(mode="json")),
                json.dumps(event.before) if event.before is not None else None,
                json.dumps(event.after) if event.after is not None else None,
                json.dumps(event.evidence_links),
                event.retention_until,
                event.note,
                event.prev_hash,
                event.event_hash,
            ),
        )
    if commit:
        conn.commit()
    return event.model_dump(mode="json")


def list_audit_events(
    conn,
    *,
    date_from: date | None = None,
    date_to: date | None = None,
    module: str | None = None,
    username: str | None = None,
    entity_type: str | None = None,
    action: str | None = None,
    limit: int = 200,
    offset: int = 0,
) -> dict[str, Any]:
    ensure_audit_storage(conn)
    where_clauses = ["1=1"]
    params: list[Any] = []

    if date_from is not None:
        where_clauses.append("occurred_at::date >= %s")
        params.append(date_from)
    if date_to is not None:
        where_clauses.append("occurred_at::date <= %s")
        params.append(date_to)
    if module:
        where_clauses.append("module = %s")
        params.append(module)
    if username:
        where_clauses.append("actor_json->>'username' ILIKE %s")
        params.append(f"%{username}%")
    if entity_type:
        where_clauses.append("entity_type = %s")
        params.append(entity_type)
    if action:
        where_clauses.append("action = %s")
        params.append(action)

    where_sql = " AND ".join(where_clauses)

    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT COUNT(*)
            FROM audit_events
            WHERE {where_sql}
            """,
            tuple(params),
        )
        total = int(cur.fetchone()[0] or 0)

        cur.execute(
            f"""
            SELECT
                event_id,
                occurred_at,
                module,
                entity_type,
                entity_id,
                action,
                source,
                correlation_id,
                actor_json,
                before_json,
                after_json,
                evidence_links,
                retention_until,
                note,
                prev_hash,
                event_hash
            FROM audit_events
            WHERE {where_sql}
            ORDER BY occurred_at DESC, audit_event_pk DESC
            LIMIT %s OFFSET %s
            """,
            tuple([*params, limit, offset]),
        )
        rows = cur.fetchall() or []

    items = []
    for row in rows:
        items.append(
            {
                "event_id": row[0],
                "occurred_at": row[1],
                "module": row[2],
                "entity_type": row[3],
                "entity_id": row[4],
                "action": row[5],
                "source": row[6],
                "correlation_id": row[7],
                "actor": row[8],
                "before": row[9],
                "after": row[10],
                "evidence_links": row[11],
                "retention_until": row[12],
                "note": row[13],
                "prev_hash": row[14],
                "event_hash": row[15],
            }
        )

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": items,
    }


def list_audit_packages(
    conn,
    *,
    fiscal_year: int | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    ensure_audit_storage(conn)
    where = "WHERE fiscal_year = %s" if fiscal_year is not None else ""
    params: list[Any] = [fiscal_year] if fiscal_year is not None else []

    with conn.cursor() as cur:
        cur.execute(
            f"SELECT COUNT(*) FROM audit_package_runs {where}",
            tuple(params),
        )
        total = int(cur.fetchone()[0] or 0)
        cur.execute(
            f"""
            SELECT package_id, package_name, package_mode, fiscal_year,
                   generated_at, generated_by, generated_by_name,
                   overall_status, content_hash, zip_path, notes_path
            FROM audit_package_runs
            {where}
            ORDER BY generated_at DESC, package_run_id DESC
            LIMIT %s OFFSET %s
            """,
            tuple([*params, limit, offset]),
        )
        rows = cur.fetchall() or []

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": [
            {
                "package_id": r[0],
                "package_name": r[1],
                "package_mode": r[2],
                "fiscal_year": r[3],
                "generated_at": r[4],
                "generated_by": r[5],
                "generated_by_name": r[6],
                "overall_status": r[7],
                "content_hash": r[8],
                "zip_path": r[9],
                "notes_path": r[10],
            }
            for r in rows
        ],
    }


def get_audit_package(conn, package_id: str) -> dict[str, Any] | None:
    ensure_audit_storage(conn)
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT package_id, package_name, package_mode, fiscal_year,
                   generated_at, generated_by, generated_by_name,
                   overall_status, content_hash, zip_path, notes_path
            FROM audit_package_runs
            WHERE package_id = %s
            """,
            (package_id,),
        )
        row = cur.fetchone()
    if not row:
        return None
    return {
        "package_id": row[0],
        "package_name": row[1],
        "package_mode": row[2],
        "fiscal_year": row[3],
        "generated_at": row[4],
        "generated_by": row[5],
        "generated_by_name": row[6],
        "overall_status": row[7],
        "content_hash": row[8],
        "zip_path": row[9],
        "notes_path": row[10],
    }


def _finding(
    check_id: str,
    status: AuditStatus,
    severity: str,
    message: str,
    affected_record_ids: list[str] | None = None,
    suggested_fix_steps: list[str] | None = None,
    data_sources: list[str] | None = None,
    requires_confirmation: bool = False,
) -> AuditCheckFinding:
    return AuditCheckFinding(
        check_id=check_id,
        status=status,
        severity=severity,
        message=message,
        affected_record_ids=affected_record_ids or [],
        suggested_fix_steps=suggested_fix_steps or [],
        data_sources=data_sources or [],
        requires_confirmation=requires_confirmation,
    )


def _check_employee_identity(conn) -> AuditCheckFinding:
    if not _table_exists(conn, "employees"):
        return _finding(
            "employee-identity",
            "WARN",
            "medium",
            "Employees table not found; employee identity completeness requires confirmation.",
            requires_confirmation=True,
            suggested_fix_steps=["Confirm employee master table name and SIN/TD1 fields."],
        )

    sin_col = _first_existing_column(conn, "employees", ["sin", "sin_number", "sin_no"])
    td1_col = _first_existing_column(
        conn,
        "employees",
        ["td1_province", "province_of_employment", "province", "tax_province"],
    )
    if not sin_col or not td1_col:
        return _finding(
            "employee-identity",
            "WARN",
            "medium",
            "Employee identity fields are not standardized enough to verify completeness automatically; requires confirmation.",
            requires_confirmation=True,
            suggested_fix_steps=["Standardize SIN and province-of-employment fields in employees."],
            data_sources=["employees"],
        )

    sql = f"""
        SELECT COALESCE(id::text, employee_id::text),
               COALESCE({sin_col}::text, ''),
               COALESCE({td1_col}::text, '')
        FROM employees
        WHERE COALESCE({sin_col}::text, '') = ''
           OR COALESCE({td1_col}::text, '') = ''
        LIMIT 50
    """
    with conn.cursor() as cur:
        cur.execute(sql)
        rows = cur.fetchall()
    if rows:
        return _finding(
            "employee-identity",
            "FAIL",
            "high",
            "Employee identity setup is incomplete for one or more records.",
            [str(r[0]) for r in rows],
            ["Populate SIN and province-of-employment fields.", "Re-run payroll setup checks."],
            ["employees"],
        )
    return _finding(
        "employee-identity",
        "PASS",
        "low",
        "Employee identity fields are populated for the sampled schema.",
        data_sources=["employees"],
    )


def _check_pd7a_reconciliation(conn, fiscal_year: int) -> AuditCheckFinding:
    if not _table_exists(conn, "cra_pd7a_returns"):
        return _finding(
            "pd7a-reconciliation",
            "WARN",
            "medium",
            "PD7A table not found; remittance reconciliation requires confirmation.",
            requires_confirmation=True,
            data_sources=["cra_pd7a_returns"],
        )
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT reporting_month,
                   COALESCE(total_remittance_due, 0),
                   COALESCE(adjusted_remittance, 0),
                   COALESCE(income_tax_deducted, 0),
                   COALESCE(cpp_total, 0),
                   COALESCE(ei_total, 0)
            FROM cra_pd7a_returns
            WHERE reporting_year = %s
            ORDER BY reporting_month
            """,
            (fiscal_year,),
        )
        rows = cur.fetchall()
    if not rows:
        return _finding(
            "pd7a-reconciliation",
            "WARN",
            "medium",
            f"No PD7A rows found for {fiscal_year}; remittance tie-out cannot be proven.",
            requires_confirmation=True,
            data_sources=["cra_pd7a_returns"],
        )
    mismatches = []
    for month, due, adjusted, income_tax, cpp, ei in rows:
        expected = float(income_tax or 0) + float(cpp or 0) + float(ei or 0)
        actual = float(adjusted or due or 0)
        if round(expected, 2) != round(actual, 2):
            mismatches.append(f"{month}")
    if mismatches:
        return _finding(
            "pd7a-reconciliation",
            "FAIL",
            "high",
            f"PD7A remittance amounts do not tie for months: {', '.join(mismatches)}.",
            mismatches,
            ["Reconcile remittance due against payroll deductions withheld.", "Correct PD7A totals before filing."],
            ["cra_pd7a_returns"],
        )
    return _finding(
        "pd7a-reconciliation",
        "PASS",
        "low",
        f"PD7A remittance totals tie for {len(rows)} month rows in {fiscal_year}.",
        data_sources=["cra_pd7a_returns"],
    )


def _check_t4_reconciliation(conn, fiscal_year: int) -> AuditCheckFinding:
    if not (_table_exists(conn, "employee_t4_records") or _table_exists(conn, "t4_entries")):
        return _finding(
            "t4-reconciliation",
            "WARN",
            "medium",
            "No T4 storage table found; T4 tie-out requires confirmation.",
            requires_confirmation=True,
            data_sources=["employee_t4_records", "t4_entries"],
        )
    if not _table_exists(conn, "driver_payroll"):
        return _finding(
            "t4-reconciliation",
            "WARN",
            "medium",
            "driver_payroll is missing; auto-calculated T4 tie-out requires confirmation.",
            requires_confirmation=True,
            data_sources=["driver_payroll"],
        )
    table_name = "employee_t4_records" if _table_exists(conn, "employee_t4_records") else "t4_entries"
    box14_col = (
        "box_14_employment_income"
        if table_name == "employee_t4_records"
        else "t4_box_14"
    )
    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT employee_id, COALESCE({box14_col}, 0)
            FROM {table_name}
            WHERE tax_year = %s
            """,
            (fiscal_year,),
        )
        rows = cur.fetchall()
    if not rows:
        return _finding(
            "t4-reconciliation",
            "WARN",
            "medium",
            f"No T4 rows found for {fiscal_year}; tie-out cannot be proven.",
            requires_confirmation=True,
            data_sources=[table_name],
        )
    return _finding(
        "t4-reconciliation",
        "PASS",
        "low",
        f"T4 records exist for {len(rows)} employees; automated box tie-out requires business confirmation of source mappings.",
        [str(r[0]) for r in rows[:20]],
        ["Confirm which payroll table is authoritative for T4 box 14 tie-out.", "Compare stored T4 boxes against payroll extracts."],
        [table_name, "driver_payroll"],
        requires_confirmation=True,
    )


def _check_invoice_and_trip_uniqueness(conn) -> list[AuditCheckFinding]:
    findings: list[AuditCheckFinding] = []
    if _table_exists(conn, "invoices"):
        invoice_col = _first_existing_column(conn, "invoices", ["invoice_number", "invoice_no", "number"])
        if invoice_col:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT {invoice_col}::text, COUNT(*)
                    FROM invoices
                    WHERE COALESCE({invoice_col}::text, '') <> ''
                    GROUP BY 1
                    HAVING COUNT(*) > 1
                    ORDER BY COUNT(*) DESC
                    LIMIT 50
                    """
                )
                rows = cur.fetchall()
            if rows:
                findings.append(
                    _finding(
                        "invoice-duplicates",
                        "FAIL",
                        "high",
                        "Duplicate invoice numbers detected.",
                        [str(r[0]) for r in rows],
                        ["Resolve duplicate invoice numbering before year-end package generation."],
                        ["invoices"],
                    )
                )
            else:
                findings.append(
                    _finding(
                        "invoice-duplicates",
                        "PASS",
                        "low",
                        "No duplicate invoice numbers found in the current dataset sample.",
                        data_sources=["invoices"],
                    )
                )
        else:
            findings.append(
                _finding(
                    "invoice-duplicates",
                    "WARN",
                    "medium",
                    "Invoice number column is not standardized; duplicate detection requires confirmation.",
                    requires_confirmation=True,
                    data_sources=["invoices"],
                )
            )
    else:
        findings.append(
            _finding(
                "invoice-duplicates",
                "WARN",
                "medium",
                "Invoices table not found; invoice completeness requires confirmation.",
                requires_confirmation=True,
                data_sources=["invoices"],
            )
        )

    if _table_exists(conn, "charters"):
        reserve_col = _first_existing_column(conn, "charters", ["reserve_number", "reserve_no"])
        trip_col = _first_existing_column(conn, "charters", ["charter_id", "trip_id"])
        if reserve_col:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT {reserve_col}::text, COUNT(*)
                    FROM charters
                    WHERE COALESCE({reserve_col}::text, '') <> ''
                    GROUP BY 1
                    HAVING COUNT(*) > 1
                    ORDER BY COUNT(*) DESC
                    LIMIT 50
                    """
                )
                rows = cur.fetchall()
            if rows:
                findings.append(
                    _finding(
                        "trip-duplicates",
                        "FAIL",
                        "high",
                        "Duplicate reserve/trip identifiers detected in charters.",
                        [str(r[0]) for r in rows],
                        ["Resolve duplicate trip identifiers before packaging."],
                        ["charters"],
                    )
                )
            else:
                findings.append(
                    _finding(
                        "trip-duplicates",
                        "PASS",
                        "low",
                        "No duplicate charter reserve numbers found in the current dataset sample.",
                        data_sources=["charters"],
                    )
                )
        else:
            findings.append(
                _finding(
                    "trip-duplicates",
                    "WARN",
                    "medium",
                    "Charter reserve/trip identifier column is not standardized; duplicate detection requires confirmation.",
                    requires_confirmation=True,
                    data_sources=["charters"],
                )
            )
        if trip_col is None:
            findings.append(
                _finding(
                    "trip-coverage",
                    "WARN",
                    "medium",
                    "Trip identifier field is not standardized; trip register completeness requires confirmation.",
                    requires_confirmation=True,
                    data_sources=["charters"],
                )
            )
    return findings


def _check_period_close(conn, fiscal_year: int) -> AuditCheckFinding:
    if not _table_exists(conn, "year_end_closes"):
        return _finding(
            "period-close-lock",
            "WARN",
            "medium",
            "year_end_closes table not found; close-lock enforcement requires confirmation.",
            requires_confirmation=True,
            data_sources=["year_end_closes"],
        )
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT fiscal_year, status, closed_at
            FROM year_end_closes
            WHERE fiscal_year = %s
            """,
            (fiscal_year,),
        )
        row = cur.fetchone()
    if not row:
        return _finding(
            "period-close-lock",
            "WARN",
            "medium",
            f"No year-end close exists for {fiscal_year}; post-close mutation lock cannot be proven.",
            requires_confirmation=True,
            data_sources=["year_end_closes"],
        )
    return _finding(
        "period-close-lock",
        "PASS",
        "low",
        f"Year-end close record exists for {fiscal_year} with status {row[1]}.",
        [str(fiscal_year)],
        ["Confirm whether post-close modification prevention is enforced at the router and DB layer."],
        ["year_end_closes"],
        requires_confirmation=True,
    )


def _check_audit_trail_storage(conn) -> AuditCheckFinding:
    if not _table_exists(conn, "audit_events"):
        return _finding(
            "audit-trail",
            "FAIL",
            "critical",
            "audit_events table is missing; core financial audit trail is not yet implemented.",
            suggested_fix_steps=["Create audit_events storage and wire mutation logging into write paths."],
            data_sources=["audit_events"],
        )
    count = _safe_count(conn, "SELECT COUNT(*) FROM audit_events")
    if count <= 0:
        return _finding(
            "audit-trail",
            "WARN",
            "high",
            "audit_events table exists but contains no rows yet; mutation logging coverage remains to be wired.",
            requires_confirmation=True,
            suggested_fix_steps=["Attach audit-event writes to financial, payroll, and year-end mutations."],
            data_sources=["audit_events"],
        )
    return _finding(
        "audit-trail",
        "PASS",
        "low",
        f"audit_events contains {count} entries.",
        data_sources=["audit_events"],
    )


def _check_package_retention(conn) -> AuditCheckFinding:
    if not _table_exists(conn, "audit_package_runs"):
        return _finding(
            "package-retention",
            "FAIL",
            "high",
            "audit_package_runs table is missing; year-end package retention cannot be proven.",
            suggested_fix_steps=["Create audit_package_runs storage and persist package manifests."],
            data_sources=["audit_package_runs"],
        )
    count = _safe_count(conn, "SELECT COUNT(*) FROM audit_package_runs")
    return _finding(
        "package-retention",
        "PASS",
        "low",
        f"audit_package_runs contains {count} package records and supports 6+ year retention tracking.",
        data_sources=["audit_package_runs"],
    )


def _check_impossible_values(conn, fiscal_year: int) -> list[AuditCheckFinding]:
    findings: list[AuditCheckFinding] = []

    if _table_exists(conn, "payments"):
        bad_payments = _safe_count(
            conn,
            """
            SELECT COUNT(*)
            FROM payments
            WHERE COALESCE(amount, 0) < 0
            """,
        )
        findings.append(
            _finding(
                "payment-negative-values",
                "FAIL" if bad_payments else "PASS",
                "high" if bad_payments else "low",
                (
                    f"Found {bad_payments} negative payment rows; verify reversals are represented explicitly."
                    if bad_payments
                    else "No negative payment values detected."
                ),
                data_sources=["payments"],
                suggested_fix_steps=[
                    "Reverse using explicit payment reversal events instead of negative operational rows.",
                    "Correct incorrect sign errors in payments.amount.",
                ]
                if bad_payments
                else [],
            )
        )

    if _table_exists(conn, "invoices"):
        bad_invoices = _safe_count(
            conn,
            """
            SELECT COUNT(*)
            FROM invoices
            WHERE COALESCE(invoice_total, 0) < 0
            """,
        )
        findings.append(
            _finding(
                "invoice-negative-totals",
                "FAIL" if bad_invoices else "PASS",
                "high" if bad_invoices else "low",
                (
                    f"Found {bad_invoices} invoices with negative totals; verify credit-note handling."
                    if bad_invoices
                    else "No negative invoice totals detected."
                ),
                data_sources=["invoices"],
                suggested_fix_steps=[
                    "Use explicit credit-note/void workflow and keep invoice totals non-negative.",
                    "Investigate negative invoice_total rows.",
                ]
                if bad_invoices
                else [],
            )
        )

    if _table_exists(conn, "cra_pd7a_returns"):
        pd7a_total = _safe_count(
            conn,
            """
            SELECT COUNT(*)
            FROM cra_pd7a_returns
            WHERE reporting_year = %s
              AND COALESCE(total_remittance_due, 0) < 0
            """,
            (fiscal_year,),
        )
        findings.append(
            _finding(
                "pd7a-negative-remittance",
                "FAIL" if pd7a_total else "PASS",
                "high" if pd7a_total else "low",
                (
                    f"Found {int(pd7a_total)} PD7A rows with negative remittance totals."
                    if pd7a_total
                    else "No negative PD7A remittance totals detected."
                ),
                data_sources=["cra_pd7a_returns"],
                suggested_fix_steps=["Correct PD7A totals before filing."]
                if pd7a_total
                else [],
            )
        )

    if not findings:
        findings.append(
            _finding(
                "impossible-values",
                "WARN",
                "medium",
                "No known financial tables were available for impossible-value checks; requires confirmation.",
                requires_confirmation=True,
                data_sources=["payments", "invoices", "cra_pd7a_returns"],
            )
        )

    return findings


def _check_audit_coverage(conn) -> AuditCheckFinding:
    if not _table_exists(conn, "audit_events"):
        return _finding(
            "audit-coverage",
            "FAIL",
            "critical",
            "audit_events table is missing; cannot verify mutation coverage.",
            suggested_fix_steps=["Create audit_events and wire mutation routes."],
            data_sources=["audit_events"],
        )

    expected_actions = [
        ("invoices", "create_invoice"),
        ("invoices", "update_invoice"),
        ("invoices", "mark_paid"),
        ("invoices", "delete_invoice"),
        ("payments", "create_payment"),
        ("payments", "update_payment"),
        ("payments", "delete_payment"),
        ("receipts", "create_receipt"),
        ("receipts", "update_receipt"),
        ("receipts", "delete_receipt"),
        ("bookings", "create_booking"),
        ("bookings", "update_booking"),
        ("charters", "update_charter"),
        ("charters", "create_charter_route"),
        ("charters", "update_charter_route"),
        ("charters", "delete_charter_route"),
        ("charters", "reorder_charter_routes"),
        ("employees", "employee_created"),
        ("employees", "employee_updated"),
        ("vehicles", "vehicle_created"),
        ("vehicles", "vehicle_updated"),
        ("beverage_reconciliation", "beverage_reconciliation_created"),
        ("beverage_reconciliation", "beverage_reconciliation_updated"),
        ("file_storage", "upload_file"),
        ("file_storage", "download_file"),
        ("file_storage", "delete_file"),
        ("file_storage", "create_employee_folder"),
        ("file_storage", "create_vehicle_folder"),
        ("banking", "categorize_transaction"),
        ("banking", "update_banking_transaction"),
        ("banking_allocations", "allocate_banking_to_receipts"),
        ("reports", "create_accounting_rule"),
        ("reports", "update_accounting_rule"),
        ("reports", "delete_accounting_rule"),
        ("reports", "reclassify_receipts_gl"),
        ("reports", "reclassify_ledger_rows"),
        ("reconciliation_report", "link_banking_to_receipt"),
        ("reconciliation_report", "update_receipt_field_inline"),
        ("charges", "create_charge"),
        ("charges", "update_charge"),
        ("charges", "delete_charge"),
        ("cash_box", "create_transaction"),
        ("cash_box", "update_transaction"),
        ("cash_box", "delete_transaction"),
        ("payroll_entries", "create_entry"),
        ("payroll_entries", "update_entry"),
        ("payroll_entries", "delete_entry"),
        ("payroll_compliance", "pd7a_upsert"),
        ("payroll_compliance", "pd7a_update"),
        ("payroll_compliance", "pd7a_submit"),
        ("year_end", "year_end_closed"),
    ]

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT module, action, COUNT(*)
            FROM audit_events
            GROUP BY module, action
            """
        )
        rows = cur.fetchall() or []
    observed = {(str(r[0]), str(r[1])): int(r[2] or 0) for r in rows}
    missing = [f"{mod}.{act}" for mod, act in expected_actions if observed.get((mod, act), 0) <= 0]

    if missing:
        return _finding(
            "audit-coverage",
            "WARN",
            "medium",
            "Expected mutation audit events are missing for one or more workflows.",
            affected_record_ids=missing,
            suggested_fix_steps=[
                "Wire missing mutation routes to record_audit_event.",
                "Backfill historical events only if policy allows and source truth is available.",
            ],
            data_sources=["audit_events"],
            requires_confirmation=True,
        )

    return _finding(
        "audit-coverage",
        "PASS",
        "low",
        "All currently expected core mutation audit events are present.",
        data_sources=["audit_events"],
    )


def generate_audit_check_report(
    conn, request: AuditCheckRequest
) -> AuditCheckReport:
    ensure_audit_storage(conn)
    findings = [
        _check_employee_identity(conn),
        _check_pd7a_reconciliation(conn, request.fiscal_year),
        _check_t4_reconciliation(conn, request.fiscal_year),
        *_check_invoice_and_trip_uniqueness(conn),
        _check_period_close(conn, request.fiscal_year),
        _check_audit_trail_storage(conn),
        _check_audit_coverage(conn),
        _check_package_retention(conn),
        *_check_impossible_values(conn, request.fiscal_year),
    ]

    severity_rank = {"PASS": 0, "WARN": 1, "FAIL": 2}
    overall = "PASS"
    for finding in findings:
        if severity_rank[finding.status] > severity_rank[overall]:
            overall = finding.status
    summary = dict(Counter(finding.status for finding in findings))
    report = AuditCheckReport(
        fiscal_year=request.fiscal_year,
        overall_status=overall,
        findings=findings,
        summary=summary,
        correlation_id=request.correlation_id,
    )

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO audit_check_runs (
                run_id, fiscal_year, generated_by, correlation_id,
                overall_status, summary_json, findings_json
            ) VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s::jsonb)
            ON CONFLICT (run_id) DO NOTHING
            """,
            (
                hashlib.sha256(
                    f"{request.fiscal_year}:{request.correlation_id or ''}:{datetime.utcnow().isoformat()}".encode(
                        "utf-8"
                    )
                ).hexdigest(),
                request.fiscal_year,
                request.generated_by,
                request.correlation_id,
                report.overall_status,
                json.dumps(report.summary),
                json.dumps([f.model_dump(mode="json") for f in findings]),
            ),
        )
    conn.commit()
    return report


def audit_schema_json() -> dict[str, Any]:
    return AUDIT_EVENT_SCHEMA
