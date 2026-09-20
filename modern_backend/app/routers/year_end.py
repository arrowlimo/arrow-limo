import json
from datetime import date, datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from ..audit.engine import ensure_audit_storage, record_audit_event
from ..audit.schemas import AuditEvent, AuditEventActor
from ..db import get_connection, return_connection

router = APIRouter(prefix="/api/year-end", tags=["year_end_close"])


class YearEndChecklistItem(BaseModel):
    item_id: int = Field(ge=1, le=1000)
    title: str = Field(min_length=2, max_length=200)
    description: str = Field(default="", max_length=500)
    completed: bool = False


class YearEndCloseRequest(BaseModel):
    fiscal_year: int = Field(ge=2000, le=2100)
    force: bool = False
    finalize: bool = False
    notes: str | None = Field(default=None, max_length=1000)


class YearEndReopenRequest(BaseModel):
    fiscal_year: int = Field(ge=2000, le=2100)
    notes: str | None = Field(default=None, max_length=1000)


def _ensure_tables(conn) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS year_end_closes (
                close_id SERIAL PRIMARY KEY,
                fiscal_year INTEGER UNIQUE NOT NULL,
                status TEXT NOT NULL DEFAULT 'closed',
                total_revenue NUMERIC NOT NULL DEFAULT 0,
                total_expenses NUMERIC NOT NULL DEFAULT 0,
                net_income NUMERIC NOT NULL DEFAULT 0,
                retained_earnings_rollover NUMERIC NOT NULL DEFAULT 0,
                capital_gains NUMERIC NOT NULL DEFAULT 0,
                notes TEXT,
                executed_by TEXT,
                closed_at TIMESTAMP NOT NULL DEFAULT NOW(),
                summary_json JSONB
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS year_end_checklist (
                fiscal_year INTEGER NOT NULL,
                item_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                completed BOOLEAN NOT NULL DEFAULT FALSE,
                updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
                PRIMARY KEY (fiscal_year, item_id)
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS year_end_rollovers (
                rollover_id SERIAL PRIMARY KEY,
                fiscal_year INTEGER NOT NULL,
                account_code TEXT,
                account_name TEXT,
                amount NUMERIC NOT NULL,
                direction TEXT NOT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                metadata JSONB
            )
            """
        )
    conn.commit()


def _has_column(conn, table: str, column: str) -> bool:
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
            (table, column),
        )
        return cur.fetchone() is not None


def _date_bounds(fiscal_year: int) -> tuple[date, date]:
    return date(fiscal_year, 1, 1), date(fiscal_year, 12, 31)


def _compute_summary(conn, fiscal_year: int) -> dict[str, float]:
    start_date, end_date = _date_bounds(fiscal_year)

    charter_date_col = (
        "charter_date"
        if _has_column(conn, "charters", "charter_date")
        else "pickup_date"
        if _has_column(conn, "charters", "pickup_date")
        else None
    )
    revenue_col = (
        "grand_total"
        if _has_column(conn, "charters", "grand_total")
        else "total_amount_due"
        if _has_column(conn, "charters", "total_amount_due")
        else None
    )

    total_revenue = 0.0
    if charter_date_col and revenue_col:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT COALESCE(SUM({revenue_col}), 0)
                FROM charters
                WHERE {charter_date_col} BETWEEN %s AND %s
                """,
                (start_date, end_date),
            )
            total_revenue = float(cur.fetchone()[0] or 0.0)

    receipt_date_col = (
        "receipt_date"
        if _has_column(conn, "receipts", "receipt_date")
        else "date"
        if _has_column(conn, "receipts", "date")
        else None
    )
    expense_col = (
        "gross_amount"
        if _has_column(conn, "receipts", "gross_amount")
        else "amount"
        if _has_column(conn, "receipts", "amount")
        else None
    )

    total_expenses = 0.0
    if receipt_date_col and expense_col:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT COALESCE(SUM({expense_col}), 0)
                FROM receipts
                WHERE {receipt_date_col} BETWEEN %s AND %s
                """,
                (start_date, end_date),
            )
            total_expenses = float(cur.fetchone()[0] or 0.0)

    net_income = total_revenue - total_expenses
    return {
        "total_revenue": round(total_revenue, 2),
        "total_expenses": round(total_expenses, 2),
        "net_income": round(net_income, 2),
    }


def _compute_capital_gains(conn, fiscal_year: int) -> dict[str, Any]:
    start_date, end_date = _date_bounds(fiscal_year)

    total = 0.0
    items: list[dict[str, Any]] = []

    if (
        _has_column(conn, "fixed_assets", "sold_date")
        and _has_column(conn, "fixed_assets", "sale_price")
        and _has_column(conn, "fixed_assets", "cost_basis")
    ):
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT asset_id, sold_date, sale_price, cost_basis,
                       (COALESCE(sale_price, 0) - COALESCE(cost_basis, 0)) AS gain
                FROM fixed_assets
                WHERE sold_date BETWEEN %s AND %s
                """,
                (start_date, end_date),
            )
            rows = cur.fetchall()
        for r in rows:
            gain = float(r[4] or 0.0)
            total += gain
            items.append(
                {
                    "source": "fixed_assets",
                    "asset_id": r[0],
                    "date": str(r[1]),
                    "sale_price": float(r[2] or 0.0),
                    "cost_basis": float(r[3] or 0.0),
                    "gain": round(gain, 2),
                }
            )
    return {"capital_gains": round(total, 2), "items": items}


def _compute_payroll_summary(conn, fiscal_year: int) -> dict[str, Any]:
        """Summarize payroll, T4, and remittance balances for the fiscal year."""

        summary = {
            "gross_payroll": 0.0,
            "t4_employment_income": 0.0,
            "t4_employee_count": 0,
            "pd7a_due": 0.0,
            "pd7a_paid": 0.0,
            "pd7a_outstanding": 0.0,
            "payroll_remittances_paid": 0.0,
            "payroll_entries_gross": 0.0,
            "driver_payroll_gross": 0.0,
        }

        with conn.cursor() as cur:
            if _has_column(conn, "driver_payroll", "year") and _has_column(conn, "driver_payroll", "gross_pay"):
                cur.execute(
                    """
                    SELECT COALESCE(SUM(COALESCE(gross_pay, 0)), 0)
                    FROM driver_payroll
                    WHERE year = %s
                    """,
                    (fiscal_year,),
                )
                summary["driver_payroll_gross"] = float(cur.fetchone()[0] or 0.0)

            if _has_column(conn, "payroll_entries", "year"):
                cur.execute(
                    """
                    SELECT COALESCE(SUM(
                        COALESCE(base_salary, 0)
                        + COALESCE(bonus, 0)
                        + COALESCE(gratuity, 0)
                        + COALESCE(other_benefits, 0)
                    ), 0)
                    FROM payroll_entries
                    WHERE year = %s
                    """,
                    (fiscal_year,),
                )
                summary["payroll_entries_gross"] = float(cur.fetchone()[0] or 0.0)

            if _has_column(conn, "employee_t4_records", "tax_year") and _has_column(
                conn, "employee_t4_records", "box_14_employment_income"
            ):
                cur.execute(
                    """
                    SELECT COUNT(*), COALESCE(SUM(COALESCE(box_14_employment_income, 0)), 0)
                    FROM employee_t4_records
                    WHERE tax_year = %s
                    """,
                    (fiscal_year,),
                )
                row = cur.fetchone()
                summary["t4_employee_count"] = int(row[0] or 0)
                summary["t4_employment_income"] = float(row[1] or 0.0)

            if _has_column(conn, "cra_pd7a_returns", "reporting_year"):
                cur.execute(
                    """
                    SELECT
                        COALESCE(SUM(COALESCE(total_remittance_due, 0)), 0),
                        COALESCE(SUM(COALESCE(adjusted_remittance, total_remittance_due, 0)), 0)
                    FROM cra_pd7a_returns
                    WHERE reporting_year = %s
                    """,
                    (fiscal_year,),
                )
                row = cur.fetchone()
                summary["pd7a_due"] = float(row[0] or 0.0)
                summary["pd7a_paid"] = float(row[1] or 0.0)

            if _has_column(conn, "payroll_remittances", "fiscal_year"):
                cur.execute(
                    """
                    SELECT COALESCE(SUM(COALESCE(payment_amount, 0)), 0)
                    FROM payroll_remittances
                    WHERE fiscal_year = %s
                    """,
                    (fiscal_year,),
                )
                summary["payroll_remittances_paid"] = float(cur.fetchone()[0] or 0.0)

        summary["gross_payroll"] = round(
            summary["driver_payroll_gross"] + summary["payroll_entries_gross"], 2
        )
        summary["pd7a_outstanding"] = round(
            summary["pd7a_due"] - summary["payroll_remittances_paid"], 2
        )
        summary["available_after_payroll"] = round(
            summary["gross_payroll"] - summary["pd7a_outstanding"], 2
        )
        return summary
def _get_checklist(conn, fiscal_year: int) -> list[dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT item_id, title, COALESCE(description, ''), completed, updated_at
            FROM year_end_checklist
            WHERE fiscal_year = %s
            ORDER BY item_id
            """,
            (fiscal_year,),
        )
        rows = cur.fetchall()

    return [
        {
            "item_id": r[0],
            "title": r[1],
            "description": r[2],
            "completed": bool(r[3]),
            "updated_at": r[4].isoformat() if hasattr(r[4], "isoformat") else None,
        }
        for r in rows
    ]


def _checklist_summary(items: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(items)
    completed = sum(1 for i in items if i.get("completed"))
    return {
        "total": total,
        "completed": completed,
        "all_complete": total > 0 and completed == total,
    }


def _insert_rollover_marker(conn, fiscal_year: int, net_income: float) -> dict[str, Any]:
    direction = "credit" if net_income >= 0 else "debit"
    amount = abs(net_income)

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO year_end_rollovers (
                fiscal_year, account_code, account_name,
                amount, direction, metadata
            )
            VALUES (%s, %s, %s, %s, %s, %s::jsonb)
            RETURNING rollover_id, created_at
            """,
            (
                fiscal_year,
                "3000",
                "Retained Earnings",
                amount,
                direction,
                '{"source":"year_end_close"}',
            ),
        )
        row = cur.fetchone()

    # Best-effort mirror entry in general_ledger if schema supports it.
    required_cols = [
        _has_column(conn, "general_ledger", "date"),
        _has_column(conn, "general_ledger", "transaction_type"),
        _has_column(conn, "general_ledger", "account"),
        _has_column(conn, "general_ledger", "account_name"),
        _has_column(conn, "general_ledger", "debit"),
        _has_column(conn, "general_ledger", "credit"),
    ]
    if all(required_cols):
        debit_val = amount if direction == "debit" else 0.0
        credit_val = amount if direction == "credit" else 0.0
        cols = ["date", "transaction_type", "account", "account_name", "debit", "credit"]
        vals = [
            datetime(fiscal_year, 12, 31).date(),
            "year_end_rollover",
            "3000",
            "Retained Earnings",
            debit_val,
            credit_val,
        ]

        optional = {
            "num": f"YE-{fiscal_year}",
            "name": f"Year-End Close {fiscal_year}",
            "memo_description": "Automated retained earnings rollover",
            "account_full_name": "Equity:Retained Earnings",
        }
        for col, value in optional.items():
            if _has_column(conn, "general_ledger", col):
                cols.append(col)
                vals.append(value)

        placeholders = ", ".join(["%s"] * len(vals))
        with conn.cursor() as cur:
            cur.execute(
                f"INSERT INTO general_ledger ({', '.join(cols)}) VALUES ({placeholders})",
                vals,
            )

    return {
        "rollover_id": row[0],
        "created_at": row[1].isoformat() if hasattr(row[1], "isoformat") else None,
        "direction": direction,
        "amount": round(amount, 2),
    }


def _cleanup_year_end_artifacts(conn, fiscal_year: int) -> None:
    """Remove prior auto-generated close artifacts for safe draft recalculation."""
    with conn.cursor() as cur:
        cur.execute(
            """
            DELETE FROM year_end_rollovers
            WHERE fiscal_year = %s
              AND COALESCE(metadata->>'source', '') IN (
                  'year_end_close',
                  'year_end_close_draft',
                  'year_end_close_final'
              )
            """,
            (fiscal_year,),
        )

        # Remove prior mirrored GL rollover line created by this close flow.
        if _has_column(conn, "general_ledger", "transaction_type") and _has_column(
            conn, "general_ledger", "num"
        ):
            cur.execute(
                """
                DELETE FROM general_ledger
                WHERE transaction_type = 'year_end_rollover'
                  AND num = %s
                """,
                (f"YE-{fiscal_year}",),
            )


def refresh_draft_year_end_close(conn, fiscal_year: int) -> dict[str, Any]:
    """Recompute a draft year-end close after receipt mutations.

    Finalized closes remain locked. Draft/open close rows are refreshed in place
    so newly added receipts adjust the stored totals.
    """

    _ensure_tables(conn)
    summary = _compute_summary(conn, fiscal_year)
    gains = _compute_capital_gains(conn, fiscal_year)
    payroll = _compute_payroll_summary(conn, fiscal_year)

    try:
        from .t2_returns import _refresh_t2_return_totals
    except Exception:
        _refresh_t2_return_totals = None
    if _refresh_t2_return_totals is not None:
        _refresh_t2_return_totals(conn, fiscal_year)

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT close_id, status
            FROM year_end_closes
            WHERE fiscal_year = %s
            """,
            (fiscal_year,),
        )
        row = cur.fetchone()

    if row is None:
        return {
            "fiscal_year": fiscal_year,
            "refreshed": False,
            "reason": "no_close_record",
            "summary": {
                **summary,
                "capital_gains": gains["capital_gains"],
                "payroll": payroll,
            },
        }

    status = (row[1] or "closed").strip().lower()
    if status == "finalized_closed":
        return {
            "fiscal_year": fiscal_year,
            "refreshed": False,
            "reason": "finalized_locked",
            "status": status,
            "summary": {
                **summary,
                "capital_gains": gains["capital_gains"],
                "payroll": payroll,
            },
        }

    _cleanup_year_end_artifacts(conn, fiscal_year)
    rollover = _insert_rollover_marker(conn, fiscal_year, summary["net_income"])

    summary_json = json.dumps(
        {
            "summary": {
                "total_revenue": summary["total_revenue"],
                "total_expenses": summary["total_expenses"],
                "net_income": summary["net_income"],
            },
            "capital_gains": gains["capital_gains"],
            "payroll": payroll,
        }
    )

    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE year_end_closes
            SET total_revenue = %s,
                total_expenses = %s,
                net_income = %s,
                retained_earnings_rollover = %s,
                capital_gains = %s,
                closed_at = NOW(),
                summary_json = %s::jsonb
            WHERE fiscal_year = %s
            """,
            (
                summary["total_revenue"],
                summary["total_expenses"],
                summary["net_income"],
                rollover["amount"],
                gains["capital_gains"],
                summary_json,
                fiscal_year,
            ),
        )

    return {
        "fiscal_year": fiscal_year,
        "refreshed": True,
        "status": status,
        "summary": {
            **summary,
            "capital_gains": gains["capital_gains"],
            "payroll": payroll,
            "retained_earnings_rollover": rollover["amount"],
            "rollover_direction": rollover["direction"],
        },
    }


def _audit_actor(request: Request) -> AuditEventActor:
    user = getattr(request.state, "current_user", None) or {}
    return AuditEventActor(
        actor_type="user" if user else "service",
        user_id=str(user.get("user_id") or user.get("employee_id") or "") or None,
        username=user.get("username") or user.get("name"),
        role=user.get("role"),
    )


@router.get("/summary/{fiscal_year}")
def get_year_end_summary(fiscal_year: int):
    conn = get_connection()
    try:
        _ensure_tables(conn)
        return {
            "fiscal_year": fiscal_year,
            **_compute_summary(conn, fiscal_year),
            "payroll": _compute_payroll_summary(conn, fiscal_year),
        }
    finally:
        return_connection(conn)


@router.get("/capital-gains/{fiscal_year}")
def get_capital_gains(fiscal_year: int):
    conn = get_connection()
    try:
        _ensure_tables(conn)
        data = _compute_capital_gains(conn, fiscal_year)
        return {"fiscal_year": fiscal_year, **data}
    finally:
        return_connection(conn)


@router.get("/checklist/{fiscal_year}")
def get_year_end_checklist(fiscal_year: int):
    conn = get_connection()
    try:
        _ensure_tables(conn)
        items = _get_checklist(conn, fiscal_year)
        return {
            "fiscal_year": fiscal_year,
            "items": items,
            "summary": _checklist_summary(items),
        }
    finally:
        return_connection(conn)


@router.post("/checklist/{fiscal_year}")
def upsert_year_end_checklist_item(fiscal_year: int, item: YearEndChecklistItem):
    conn = get_connection()
    try:
        _ensure_tables(conn)
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO year_end_checklist (
                    fiscal_year, item_id, title, description, completed, updated_at
                )
                VALUES (%s, %s, %s, %s, %s, NOW())
                ON CONFLICT (fiscal_year, item_id)
                DO UPDATE SET
                    title = EXCLUDED.title,
                    description = EXCLUDED.description,
                    completed = EXCLUDED.completed,
                    updated_at = NOW()
                """,
                (
                    fiscal_year,
                    item.item_id,
                    item.title.strip(),
                    item.description.strip(),
                    item.completed,
                ),
            )
        conn.commit()
        return {"status": "saved", "fiscal_year": fiscal_year, "item_id": item.item_id}
    except Exception as exc:
        conn.rollback()
        raise HTTPException(
            status_code=400, detail=f"failed_to_save_checklist_item: {exc}"
        ) from exc
    finally:
        return_connection(conn)


@router.get("/status/{fiscal_year}")
def get_year_end_status(fiscal_year: int):
    conn = get_connection()
    try:
        _ensure_tables(conn)
        summary = _compute_summary(conn, fiscal_year)
        gains = _compute_capital_gains(conn, fiscal_year)
        payroll = _compute_payroll_summary(conn, fiscal_year)
        checklist_items = _get_checklist(conn, fiscal_year)
        checklist = _checklist_summary(checklist_items)

        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT close_id, status, closed_at, total_revenue, total_expenses,
                       net_income, retained_earnings_rollover, capital_gains
                FROM year_end_closes
                WHERE fiscal_year = %s
                """,
                (fiscal_year,),
            )
            row = cur.fetchone()

        if row:
            status = row[1] or "closed"
            current_summary = {
                **summary,
                "capital_gains": gains["capital_gains"],
                "payroll": payroll,
                "closed_at": row[2].isoformat() if hasattr(row[2], "isoformat") else None,
            }
            return {
                "fiscal_year": fiscal_year,
                "status": status,
                "message": f"Fiscal year {fiscal_year} is {status}.",
                "summary": {
                    "total_revenue": float(row[3] or 0.0),
                    "total_expenses": float(row[4] or 0.0),
                    "net_income": float(row[5] or 0.0),
                    "retained_earnings_rollover": float(row[6] or 0.0),
                    "capital_gains": float(row[7] or 0.0),
                    "closed_at": row[2].isoformat() if hasattr(row[2], "isoformat") else None,
                },
                "current_summary": current_summary,
                "summary_matches_current": (
                    round(float(row[3] or 0.0), 2) == current_summary["total_revenue"]
                    and round(float(row[4] or 0.0), 2) == current_summary["total_expenses"]
                    and round(float(row[5] or 0.0), 2) == current_summary["net_income"]
                ),
                "checklist": checklist,
            }

        return {
            "fiscal_year": fiscal_year,
            "status": "open",
            "message": f"Fiscal year {fiscal_year} is open.",
            "summary": {
                **summary,
                "capital_gains": gains["capital_gains"],
                "payroll": payroll,
                "closed_at": None,
            },
            "checklist": checklist,
        }
    finally:
        return_connection(conn)


@router.post("/close")
def execute_year_end_close(payload: YearEndCloseRequest, request: Request):
    conn = get_connection()
    try:
        _ensure_tables(conn)
        fiscal_year = payload.fiscal_year

        with conn.cursor() as cur:
            cur.execute(
                "SELECT close_id, status FROM year_end_closes WHERE fiscal_year = %s",
                (fiscal_year,),
            )
            existing = cur.fetchone()
            if existing is not None:
                existing_status = (existing[1] or "closed").strip().lower()
                if existing_status in {"closed", "finalized_closed"}:
                    raise HTTPException(
                        status_code=400,
                        detail="year_already_finalized",
                    )

        checklist_items = _get_checklist(conn, fiscal_year)
        checklist = _checklist_summary(checklist_items)
        if checklist["total"] > 0 and (not checklist["all_complete"]) and not payload.force:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "checklist_incomplete",
                    "completed": checklist["completed"],
                    "total": checklist["total"],
                },
            )

        summary = _compute_summary(conn, fiscal_year)
        gains = _compute_capital_gains(conn, fiscal_year)
        payroll = _compute_payroll_summary(conn, fiscal_year)
        _cleanup_year_end_artifacts(conn, fiscal_year)
        rollover = _insert_rollover_marker(conn, fiscal_year, summary["net_income"])
        close_status = "finalized_closed" if payload.finalize else "draft_closed"

        with conn.cursor() as cur:
            summary_json = json.dumps(
                {
                    "summary": {
                        "total_revenue": summary["total_revenue"],
                        "total_expenses": summary["total_expenses"],
                        "net_income": summary["net_income"],
                    },
                    "capital_gains": gains["capital_gains"],
                }
            )
            cur.execute(
                """
                INSERT INTO year_end_closes (
                    fiscal_year, status, total_revenue, total_expenses,
                    net_income, retained_earnings_rollover, capital_gains,
                    notes, executed_by, closed_at, summary_json
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), %s::jsonb)
                ON CONFLICT (fiscal_year)
                DO UPDATE SET
                    status = EXCLUDED.status,
                    total_revenue = EXCLUDED.total_revenue,
                    total_expenses = EXCLUDED.total_expenses,
                    net_income = EXCLUDED.net_income,
                    retained_earnings_rollover = EXCLUDED.retained_earnings_rollover,
                    capital_gains = EXCLUDED.capital_gains,
                    notes = EXCLUDED.notes,
                    executed_by = EXCLUDED.executed_by,
                    closed_at = NOW(),
                    summary_json = EXCLUDED.summary_json
                RETURNING close_id, closed_at
                """,
                (
                    fiscal_year,
                    close_status,
                    summary["total_revenue"],
                    summary["total_expenses"],
                    summary["net_income"],
                    rollover["amount"],
                    gains["capital_gains"],
                    payload.notes,
                    "web_app",
                    summary_json,
                ),
            )
            row = cur.fetchone()

        if payload.finalize:
            ensure_audit_storage(conn)
            event = AuditEvent(
                module="year_end",
                entity_type="year_end_close",
                entity_id=str(fiscal_year),
                action="year_end_finalized",
                source="api",
                correlation_id=request.headers.get("X-Request-ID"),
                actor=_audit_actor(request),
                before={
                    "status": "draft_closed" if existing is not None else "open",
                    "force": payload.force,
                },
                after={
                    "status": close_status,
                    "summary": {
                        **summary,
                        "capital_gains": gains["capital_gains"],
                        "payroll": payroll,
                        "retained_earnings_rollover": rollover["amount"],
                    },
                    "notes": payload.notes,
                },
                evidence_links=[
                    f"year_end_closes:{fiscal_year}",
                    f"year_end_rollovers:{rollover['rollover_id']}",
                ],
                retention_until=datetime(fiscal_year + 6, 12, 31).date(),
                note="Year-end finalization audit record",
            )
            record_audit_event(conn, event, ensure_storage=False, commit=False)
        conn.commit()

        result_label = "finalized" if payload.finalize else "draft-closed"
        return {
            "status": close_status,
            "message": f"Fiscal year {fiscal_year} {result_label} successfully.",
            "summary": {
                **summary,
                "capital_gains": gains["capital_gains"],
                "payroll": payroll,
                "retained_earnings_rollover": rollover["amount"],
                "rollover_direction": rollover["direction"],
                "closed_at": row[1].isoformat() if hasattr(row[1], "isoformat") else None,
            },
        }
    except HTTPException:
        conn.rollback()
        raise
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"year_end_close_failed: {exc}") from exc
    finally:
        return_connection(conn)


@router.post("/reopen")
def reopen_year_end(payload: YearEndReopenRequest):
    conn = get_connection()
    try:
        _ensure_tables(conn)
        fiscal_year = payload.fiscal_year

        with conn.cursor() as cur:
            cur.execute(
                "SELECT status FROM year_end_closes WHERE fiscal_year = %s",
                (fiscal_year,),
            )
            row = cur.fetchone()

        if row is None:
            return {
                "status": "open",
                "message": f"Fiscal year {fiscal_year} is already open.",
            }

        status = (row[0] or "closed").strip().lower()
        if status in {"closed", "finalized_closed"}:
            raise HTTPException(
                status_code=400,
                detail="finalized_close_locked",
            )

        _cleanup_year_end_artifacts(conn, fiscal_year)
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM year_end_closes WHERE fiscal_year = %s",
                (fiscal_year,),
            )
        conn.commit()
        return {
            "status": "open",
            "message": f"Fiscal year {fiscal_year} reopened from draft.",
        }
    except HTTPException:
        conn.rollback()
        raise
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"year_end_reopen_failed: {exc}") from exc
    finally:
        return_connection(conn)


@router.get("/report/{fiscal_year}")
def get_year_end_report(fiscal_year: int):
    conn = get_connection()
    try:
        _ensure_tables(conn)
        summary = _compute_summary(conn, fiscal_year)
        gains = _compute_capital_gains(conn, fiscal_year)
        payroll = _compute_payroll_summary(conn, fiscal_year)
        checklist_items = _get_checklist(conn, fiscal_year)
        checklist = _checklist_summary(checklist_items)

        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT close_id, status, notes, executed_by, closed_at
                FROM year_end_closes
                WHERE fiscal_year = %s
                """,
                (fiscal_year,),
            )
            close_row = cur.fetchone()

            cur.execute(
                """
                SELECT rollover_id, account_code, account_name,
                       amount, direction, created_at, metadata
                FROM year_end_rollovers
                WHERE fiscal_year = %s
                ORDER BY rollover_id
                """,
                (fiscal_year,),
            )
            rollover_rows = cur.fetchall()

        rollovers = [
            {
                "rollover_id": r[0],
                "account_code": r[1],
                "account_name": r[2],
                "amount": float(r[3] or 0.0),
                "direction": r[4],
                "created_at": r[5].isoformat() if hasattr(r[5], "isoformat") else None,
                "metadata": r[6],
            }
            for r in rollover_rows
        ]

        return {
            "fiscal_year": fiscal_year,
            "status": close_row[1] if close_row else "open",
            "closed": close_row is not None,
            "notes": close_row[2] if close_row else None,
            "executed_by": close_row[3] if close_row else None,
            "closed_at": close_row[4].isoformat()
            if close_row and hasattr(close_row[4], "isoformat")
            else None,
            "summary": {
                **summary,
                "capital_gains": gains["capital_gains"],
                "payroll": payroll,
            },
            "capital_gains": gains,
            "checklist": {
                "summary": checklist,
                "items": checklist_items,
            },
            "rollovers": rollovers,
        }
    finally:
        return_connection(conn)
