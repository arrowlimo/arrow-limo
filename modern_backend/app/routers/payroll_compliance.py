"""
Payroll compliance endpoints for PD7A/source deduction tracking and submission
audit.
"""

import csv
import io
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel

from ..audit.engine import ensure_audit_storage, record_audit_event
from ..audit.schemas import AuditEvent, AuditEventActor
from ..db import get_connection

router = APIRouter(
    prefix="/api/payroll-compliance", tags=["payroll-compliance"]
)


class PD7ASubmitRequest(BaseModel):
    submitted_by: str = "web_app"
    submission_reference: str | None = None
    filing_method: str = "manual"
    notes: str | None = None


class PD7AUpsertRequest(BaseModel):
    year: int
    month: int
    employee_count: int = 0
    total_gross_payroll: float = 0
    cpp_total: float = 0
    ei_total: float = 0
    income_tax_deducted: float = 0
    total_remittance_due: float | None = None
    adjusted_remittance: float | None = None
    notes: str | None = None


def _ensure_pd7a_audit_columns(conn):
    cur = conn.cursor()
    try:
        cur.execute(
            "ALTER TABLE cra_pd7a_returns ADD COLUMN IF NOT EXISTS "
            "submission_reference TEXT"
        )
        cur.execute(
            "ALTER TABLE cra_pd7a_returns ADD COLUMN IF NOT EXISTS "
            "submitted_by TEXT"
        )
        cur.execute(
            "ALTER TABLE cra_pd7a_returns ADD COLUMN IF NOT EXISTS "
            "filing_method TEXT"
        )
        conn.commit()
    finally:
        cur.close()


def _audit_actor(request: Request) -> AuditEventActor:
    user = getattr(request.state, "current_user", None) or {}
    return AuditEventActor(
        actor_type="user" if user else "service",
        user_id=str(user.get("user_id") or user.get("employee_id") or "")
        or None,
        username=user.get("username") or user.get("name"),
        role=user.get("role"),
    )


@router.post("/pd7a")
async def upsert_pd7a(
    payload: PD7AUpsertRequest,
    request: Request,
    conn=Depends(get_connection),
):
    if payload.month < 1 or payload.month > 12:
        raise HTTPException(status_code=400, detail="Month must be between 1 and 12")

    _ensure_pd7a_audit_columns(conn)
    ensure_audit_storage(conn)
    cur = conn.cursor()
    try:
        total_due = (
            payload.total_remittance_due
            if payload.total_remittance_due is not None
            else payload.cpp_total + payload.ei_total + payload.income_tax_deducted
        )
        adjusted = (
            payload.adjusted_remittance
            if payload.adjusted_remittance is not None
            else total_due
        )

        cur.execute(
            """
            SELECT id
            FROM cra_pd7a_returns
            WHERE reporting_year = %s
              AND reporting_month = %s
            """,
            (payload.year, payload.month),
        )
        existing_row = cur.fetchone()

        if existing_row:
            cur.execute(
                """
                UPDATE cra_pd7a_returns
                SET employee_count = %s,
                    total_gross_payroll = %s,
                    cpp_total = %s,
                    ei_total = %s,
                    income_tax_deducted = %s,
                    total_remittance_due = %s,
                    adjusted_remittance = %s,
                    notes = %s,
                    updated_at = NOW()
                WHERE id = %s
                """,
                (
                    payload.employee_count,
                    payload.total_gross_payroll,
                    payload.cpp_total,
                    payload.ei_total,
                    payload.income_tax_deducted,
                    total_due,
                    adjusted,
                    payload.notes,
                    existing_row[0],
                ),
            )
            action = "pd7a_updated"
        else:
            cur.execute(
                """
                INSERT INTO cra_pd7a_returns (
                    reporting_year,
                    reporting_month,
                    employee_count,
                    total_gross_payroll,
                    cpp_total,
                    ei_total,
                    income_tax_deducted,
                    total_remittance_due,
                    adjusted_remittance,
                    is_submitted,
                    notes,
                    created_at,
                    updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, FALSE, %s, NOW(), NOW())
                """,
                (
                    payload.year,
                    payload.month,
                    payload.employee_count,
                    payload.total_gross_payroll,
                    payload.cpp_total,
                    payload.ei_total,
                    payload.income_tax_deducted,
                    total_due,
                    adjusted,
                    payload.notes,
                ),
            )
            action = "pd7a_upserted"

        event = AuditEvent(
            module="payroll_compliance",
            entity_type="pd7a_return",
            entity_id=f"{payload.year}-{payload.month:02d}",
            action=action,
            source="api",
            correlation_id=request.headers.get("X-Request-ID"),
            actor=_audit_actor(request),
            before={"is_submitted": False, "exists": bool(existing_row)},
            after={
                "year": payload.year,
                "month": payload.month,
                "employee_count": payload.employee_count,
                "total_gross_payroll": payload.total_gross_payroll,
                "cpp_total": payload.cpp_total,
                "ei_total": payload.ei_total,
                "income_tax_deducted": payload.income_tax_deducted,
                "total_remittance_due": total_due,
                "adjusted_remittance": adjusted,
                "notes": payload.notes,
            },
            evidence_links=[f"cra_pd7a_returns:{payload.year}-{payload.month:02d}"],
            retention_until=date(payload.year + 6, 12, 31),
            note="PD7A row upsert audit record",
        )
        record_audit_event(conn, event, ensure_storage=False, commit=False)
        conn.commit()
        return {"success": True, "year": payload.year, "month": payload.month}
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to save PD7A row: {exc}") from exc
    finally:
        cur.close()


@router.get("/pd7a")
async def list_pd7a_all(conn=Depends(get_connection)):
    _ensure_pd7a_audit_columns(conn)
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT
                reporting_year,
                reporting_month,
                employee_count,
                total_gross_payroll,
                cpp_total,
                ei_total,
                income_tax_deducted,
                total_remittance_due,
                adjusted_remittance,
                is_submitted,
                submission_date,
                submission_reference,
                submitted_by,
                filing_method,
                notes
            FROM cra_pd7a_returns
            ORDER BY reporting_year DESC, reporting_month DESC
            """
        )
        rows = cur.fetchall()
        out = []
        for r in rows:
            out.append(
                {
                    "year": int(r[0]),
                    "month": int(r[1]),
                    "employee_count": int(r[2] or 0),
                    "total_gross_payroll": float(r[3] or 0),
                    "gross_payroll": float(r[3] or 0),
                    "cpp_total": float(r[4] or 0),
                    "ei_total": float(r[5] or 0),
                    "income_tax_deducted": float(r[6] or 0),
                    "tax_deducted": float(r[6] or 0),
                    "total_remittance_due": float(r[7] or 0),
                    "total_due": float(r[7] or 0),
                    "adjusted_remittance": float(r[8] or 0),
                    "is_submitted": bool(r[9]),
                    "submission_date": r[10].isoformat() if r[10] else None,
                    "submission_reference": r[11],
                    "submitted_by": r[12],
                    "filing_method": r[13],
                    "notes": r[14],
                }
            )
        return out
    finally:
        cur.close()


@router.post("/pd7a")
async def upsert_pd7a(
    payload: PD7AUpsertRequest,
    request: Request,
    conn=Depends(get_connection),
):
    if payload.month < 1 or payload.month > 12:
        raise HTTPException(status_code=400, detail="Month must be between 1 and 12")

    _ensure_pd7a_audit_columns(conn)
    ensure_audit_storage(conn)
    cur = conn.cursor()
    try:
        total_due = (
            payload.total_remittance_due
            if payload.total_remittance_due is not None
            else payload.cpp_total + payload.ei_total + payload.income_tax_deducted
        )
        adjusted = (
            payload.adjusted_remittance
            if payload.adjusted_remittance is not None
            else total_due
        )

        if row:
            cur.execute(
                """
                UPDATE cra_pd7a_returns
                SET employee_count = %s,
                    total_gross_payroll = %s,
                    cpp_total = %s,
                    ei_total = %s,
                    income_tax_deducted = %s,
                    total_remittance_due = %s,
                    adjusted_remittance = %s,
                    notes = %s,
                    updated_at = NOW()
                WHERE id = %s
                """,
                (
                    payload.employee_count,
                    payload.total_gross_payroll,
                    payload.cpp_total,
                    payload.ei_total,
                    payload.income_tax_deducted,
                    total_due,
                    adjusted,
                    payload.notes,
                    row[0],
                ),
            )
        else:
            cur.execute(
                """
                INSERT INTO cra_pd7a_returns (
                    reporting_year,
                    reporting_month,
                    employee_count,
                    total_gross_payroll,
                    cpp_total,
                    ei_total,
                    income_tax_deducted,
                    total_remittance_due,
                    adjusted_remittance,
                    is_submitted,
                    notes,
                    created_at,
                    updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, FALSE, %s, NOW(), NOW())
                """,
                (
                    payload.year,
                    payload.month,
                    payload.employee_count,
                    payload.total_gross_payroll,
                    payload.cpp_total,
                    payload.ei_total,
                    payload.income_tax_deducted,
                    total_due,
                    adjusted,
                    payload.notes,
                ),
            )
        conn.commit()
        return {"success": True, "year": payload.year, "month": payload.month}
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to save PD7A row: {exc}") from exc
    finally:
        cur.close()


@router.put("/pd7a/{tax_year}/{tax_month}")
async def update_pd7a_month(
    tax_year: int,
    tax_month: int,
    payload: PD7AUpsertRequest,
    request: Request,
    conn=Depends(get_connection),
):
    if tax_month < 1 or tax_month > 12:
        raise HTTPException(status_code=400, detail="Month must be between 1 and 12")

    _ensure_pd7a_audit_columns(conn)
    ensure_audit_storage(conn)
    cur = conn.cursor()
    try:
        total_due = (
            payload.total_remittance_due
            if payload.total_remittance_due is not None
            else payload.cpp_total + payload.ei_total + payload.income_tax_deducted
        )
        adjusted = (
            payload.adjusted_remittance
            if payload.adjusted_remittance is not None
            else total_due
        )

        cur.execute(
            """
            UPDATE cra_pd7a_returns
            SET employee_count = %s,
                total_gross_payroll = %s,
                cpp_total = %s,
                ei_total = %s,
                income_tax_deducted = %s,
                total_remittance_due = %s,
                adjusted_remittance = %s,
                notes = %s,
                updated_at = NOW()
            WHERE reporting_year = %s
              AND reporting_month = %s
            """,
            (
                payload.employee_count,
                payload.total_gross_payroll,
                payload.cpp_total,
                payload.ei_total,
                payload.income_tax_deducted,
                total_due,
                adjusted,
                payload.notes,
                tax_year,
                tax_month,
            ),
        )
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="PD7A row not found")

        event = AuditEvent(
            module="payroll_compliance",
            entity_type="pd7a_return",
            entity_id=f"{tax_year}-{tax_month:02d}",
            action="pd7a_updated",
            source="api",
            correlation_id=request.headers.get("X-Request-ID"),
            actor=_audit_actor(request),
            before=None,
            after={
                "year": tax_year,
                "month": tax_month,
                "employee_count": payload.employee_count,
                "total_gross_payroll": payload.total_gross_payroll,
                "cpp_total": payload.cpp_total,
                "ei_total": payload.ei_total,
                "income_tax_deducted": payload.income_tax_deducted,
                "total_remittance_due": total_due,
                "adjusted_remittance": adjusted,
                "notes": payload.notes,
            },
            evidence_links=[f"cra_pd7a_returns:{tax_year}-{tax_month:02d}"],
            retention_until=date(tax_year + 6, 12, 31),
            note="PD7A row update audit record",
        )
        record_audit_event(conn, event, ensure_storage=False, commit=False)
        conn.commit()
        return {"success": True, "year": tax_year, "month": tax_month}
    except HTTPException:
        conn.rollback()
        raise
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update PD7A row: {exc}") from exc
    finally:
        cur.close()


@router.post("/pd7a/{tax_year}/{tax_month}/submit")
async def submit_pd7a_month(
    tax_year: int,
    tax_month: int,
    payload: PD7ASubmitRequest,
    request: Request,
    conn=Depends(get_connection),
):
    if tax_month < 1 or tax_month > 12:
        raise HTTPException(
            status_code=400, detail="Month must be between 1 and 12"
        )

    _ensure_pd7a_audit_columns(conn)
    ensure_audit_storage(conn)
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT id
            FROM cra_pd7a_returns
            WHERE reporting_year = %s AND reporting_month = %s
            """,
            (tax_year, tax_month),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(
                status_code=404,
                detail="PD7A row not found for that year/month",
            )

        sub_ref = (
            payload.submission_reference or ""
        ).strip() or f"PD7A-{tax_year}{tax_month:02d}"

        cur.execute(
            """
            UPDATE cra_pd7a_returns
            SET is_submitted = TRUE,
                submission_date = CURRENT_DATE,
                submission_reference = %s,
                submitted_by = %s,
                filing_method = %s,
                notes = CASE
                    WHEN %s IS NULL OR %s = '' THEN notes
                    WHEN notes IS NULL OR notes = '' THEN %s
                    ELSE notes || E'\n' || %s
                END,
                updated_at = NOW()
            WHERE reporting_year = %s
              AND reporting_month = %s
            """,
            (
                sub_ref,
                (payload.submitted_by or "web_app").strip(),
                (payload.filing_method or "manual").strip(),
                payload.notes,
                payload.notes,
                payload.notes,
                payload.notes,
                tax_year,
                tax_month,
            ),
        )

        cur.execute(
            """
            UPDATE payroll_remittances
            SET status = 'submitted',
                pd7a_filed_date = CURRENT_DATE,
                updated_at = NOW()
            WHERE fiscal_year = %s
              AND remittance_month = %s
            """,
            (tax_year, tax_month),
        )

        event = AuditEvent(
            module="payroll_compliance",
            entity_type="pd7a_return",
            entity_id=f"{tax_year}-{tax_month:02d}",
            action="pd7a_submitted",
            source="api",
            correlation_id=request.headers.get("X-Request-ID"),
            actor=_audit_actor(request),
            before={"is_submitted": False},
            after={
                "is_submitted": True,
                "submission_reference": sub_ref,
                "submitted_by": (payload.submitted_by or "web_app").strip(),
                "filing_method": (payload.filing_method or "manual").strip(),
                "notes": payload.notes,
            },
            evidence_links=[f"cra_pd7a_returns:{tax_year}-{tax_month:02d}"],
            retention_until=date(tax_year + 6, 12, 31),
            note="PD7A submission audit record",
        )
        record_audit_event(conn, event, ensure_storage=False, commit=False)

        conn.commit()
        return {
            "success": True,
            "year": tax_year,
            "month": tax_month,
            "submission_reference": sub_ref,
            "message": "PD7A month marked submitted and remittance row"
            "updated.",
        }
    except HTTPException:
        conn.rollback()
        raise
    except Exception as exc:
        conn.rollback()
        raise HTTPException(  # noqa: B904
            status_code=500, detail=f"Failed to submit PD7A month: {exc}"
        )
    finally:
        cur.close()


@router.get("/pd7a/{tax_year}/report.csv")
async def export_pd7a_year_csv(tax_year: int, conn=Depends(get_connection)):
    _ensure_pd7a_audit_columns(conn)
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT
                reporting_year,
                reporting_month,
                employee_count,
                total_gross_payroll,
                cpp_total,
                ei_total,
                income_tax_deducted,
                total_remittance_due,
                adjusted_remittance,
                is_submitted,
                submission_date,
                submission_reference,
                submitted_by,
                filing_method,
                notes
            FROM cra_pd7a_returns
            WHERE reporting_year = %s
            ORDER BY reporting_month
            """,
            (tax_year,),
        )
        rows = cur.fetchall()

        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(
            [
                "year",
                "month",
                "employee_count",
                "gross_payroll",
                "cpp_total",
                "ei_total",
                "income_tax_deducted",
                "total_remittance_due",
                "adjusted_remittance",
                "is_submitted",
                "submission_date",
                "submission_reference",
                "submitted_by",
                "filing_method",
                "notes",
            ]
        )
        for r in rows:
            writer.writerow(
                [
                    r[0],
                    r[1],
                    r[2],
                    float(r[3] or 0),
                    float(r[4] or 0),
                    float(r[5] or 0),
                    float(r[6] or 0),
                    float(r[7] or 0),
                    float(r[8] or 0),
                    bool(r[9]),
                    r[10].isoformat() if r[10] else "",
                    r[11] or "",
                    r[12] or "",
                    r[13] or "",
                    r[14] or "",
                ]
            )

        return Response(
            content=buf.getvalue(),
            media_type="text/csv",
            headers={
                "Content-Disposition": "attachment;"
                "filename=pd7a_{tax_year}_submission_report.csv"
            },
        )
    finally:
        cur.close()
