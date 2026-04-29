"""
Payroll compliance endpoints for PD7A/source deduction tracking and submission
audit.
"""

import csv
import io

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel

from ..db import get_connection

router = APIRouter(
    prefix="/api/payroll-compliance", tags=["payroll-compliance"]
)


class PD7ASubmitRequest(BaseModel):
    submitted_by: str = "web_app"
    submission_reference: str | None = None
    filing_method: str = "manual"
    notes: str | None = None


def _ensure_pd7a_audit_columns(conn):
    cur = conn.cursor()
    try:
        cur.execute(
            "ALTER TABLE cra_pd7a_returns ADD COLUMN IF NOT EXISTS"
            "submission_reference TEXT"
        )
        cur.execute(
            "ALTER TABLE cra_pd7a_returns ADD COLUMN IF NOT EXISTS"
            "submitted_by TEXT"
        )
        cur.execute(
            "ALTER TABLE cra_pd7a_returns ADD COLUMN IF NOT EXISTS"
            "filing_method TEXT"
        )
        conn.commit()
    finally:
        cur.close()


@router.get("/pd7a/{tax_year}")
async def list_pd7a_year(tax_year: int, conn=Depends(get_connection)):
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
        out = []
        for r in rows:
            out.append(
                {
                    "year": int(r[0]),
                    "month": int(r[1]),
                    "employee_count": int(r[2] or 0),
                    "gross_payroll": float(r[3] or 0),
                    "cpp_total": float(r[4] or 0),
                    "ei_total": float(r[5] or 0),
                    "tax_deducted": float(r[6] or 0),
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


@router.post("/pd7a/{tax_year}/{tax_month}/submit")
async def submit_pd7a_month(
    tax_year: int,
    tax_month: int,
    payload: PD7ASubmitRequest,
    conn=Depends(get_connection),
):
    if tax_month < 1 or tax_month > 12:
        raise HTTPException(
            status_code=400, detail="Month must be between 1 and 12"
        )

    _ensure_pd7a_audit_columns(conn)
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
        raise HTTPException(
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
                "Content-Disposition": f"attachment;"
                "filename=pd7a_{tax_year}_submission_report.csv"
            },
        )
    finally:
        cur.close()
