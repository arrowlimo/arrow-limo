"""
Continuous employment ROE endpoints.
Provides practical ROE create/list/get/submit workflows used by frontend.
"""

import json
from datetime import date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel

from ..audit.engine import ensure_audit_storage, record_audit_event
from ..audit.schemas import AuditEvent, AuditEventActor
from ..db import get_connection

router = APIRouter(
    prefix="/api/continuous-employment", tags=["continuous-employment"]
)


class ROECreateRequest(BaseModel):
    employee_id: int
    termination_date: date
    reason_code: str = "K"
    reason_description: str | None = None


class ROESubmitRequest(BaseModel):
    submitted_by: str = "web_app"
    submission_reference: str | None = None
    notes: str | None = None


VALID_ROE_REASON_CODES = {
    "A",  # Shortage of work / End of contract or season
    "B",  # Strike or lockout
    "C",  # Return to school
    "D",  # Illness or injury
    "E",  # Quit
    "F",  # Maternity
    "G",  # Retirement
    "H",  # Work sharing
    "J",  # Apprentice training
    "K",  # Other
    "M",  # Dismissal
}

ROE_NOT_FOUND = "ROE record not found"


def _load_roe_row(cur, roe_id: int):
    cur.execute(
        """
        SELECT
            id,
            roe_number,
            employee_id,
            employee_name,
            termination_date,
            last_day_worked,
            reason_code,
            COALESCE(reason_description, ''),
            COALESCE(insurable_earnings, 0),
            COALESCE(insurable_hours, 0),
            COALESCE(roe_status, 'draft'),
            created_at,
            submitted_at,
            submitted_by,
            submission_reference,
            source_file
        FROM employee_roe_records
        WHERE id = %s
        """,
        (roe_id,),
    )
    return cur.fetchone()


def _row_to_payload(row) -> dict:
    (
        roe_id,
        roe_number,
        employee_id,
        employee_name,
        termination_date,
        last_day_worked,
        reason_code,
        reason_description,
        insurable_earnings,
        insurable_hours,
        roe_status,
        created_at,
        submitted_at,
        submitted_by,
        submission_reference,
        source_file,
    ) = row

    return {
        "roe_id": roe_id,
        "roe_number": roe_number,
        "employee_id": employee_id,
        "employee_name": employee_name,
        "termination_date": (
            termination_date.isoformat() if termination_date else None
        ),
        "last_day_paid": (
            last_day_worked.isoformat() if last_day_worked else None
        ),
        "reason_code": (reason_code or "").strip().upper(),
        "reason_description": (reason_description or "").strip(),
        "total_insurable_earnings": float(insurable_earnings or 0),
        "total_insurable_hours": float(insurable_hours or 0),
        "roe_status": roe_status,
        "created_at": created_at.isoformat() if created_at else None,
        "submitted_at": submitted_at.isoformat() if submitted_at else None,
        "submitted_by": submitted_by,
        "submission_reference": submission_reference,
        "source_file": source_file,
    }


def _validate_identity(payload: dict) -> list[str]:
    errors: list[str] = []
    if not payload.get("roe_number"):
        errors.append("Missing ROE number.")
    if not payload.get("employee_id"):
        errors.append("Missing employee_id.")
    if not (payload.get("employee_name") or "").strip():
        errors.append("Missing employee name.")
    return errors


def _validate_dates(payload: dict) -> list[str]:
    errors: list[str] = []
    today = date.today()
    termination_raw = payload.get("termination_date")
    last_day_raw = payload.get("last_day_paid")
    termination_date = (
        date.fromisoformat(termination_raw) if termination_raw else None
    )
    last_day_worked = (
        date.fromisoformat(last_day_raw) if last_day_raw else None
    )

    if termination_date is None:
        errors.append("Missing termination date.")
    elif termination_date > today:
        errors.append("Termination date cannot be in the future.")

    if last_day_worked is None:
        errors.append("Missing last day worked/paid.")
    elif termination_date and last_day_worked > termination_date:
        errors.append("Last day worked cannot be after termination date.")
    return errors


def _validate_reason(payload: dict) -> list[str]:
    errors: list[str] = []
    reason_code = (payload.get("reason_code") or "").strip().upper()
    reason_description = (payload.get("reason_description") or "").strip()

    if reason_code not in VALID_ROE_REASON_CODES:
        errors.append(f"Invalid reason code '{reason_code}'.")

    if reason_code in {"E", "K", "M"} and len(reason_description) < 5:
        errors.append(
            f"Reason description is required for code {reason_code}."
        )
    return errors


def _validate_insurable(payload: dict) -> list[str]:
    errors: list[str] = []
    if float(payload.get("total_insurable_earnings") or 0) <= 0:
        errors.append("Insurable earnings must be greater than 0.")
    if float(payload.get("total_insurable_hours") or 0) <= 0:
        errors.append("Insurable hours must be greater than 0.")
    return errors


def _build_submission_warnings(payload: dict) -> list[str]:
    warnings: list[str] = []
    created_at_raw = payload.get("created_at")
    roe_status = payload.get("roe_status")
    submitted_at = payload.get("submitted_at")
    submission_reference = payload.get("submission_reference")

    if created_at_raw and roe_status != "submitted":
        created_at = datetime.fromisoformat(created_at_raw)
        age_days = (date.today() - created_at.date()).days
        if age_days > 5:
            warnings.append(
                "ROE draft is older than 5 days; verify submission timeline"
                "compliance."
            )

    if roe_status == "submitted" and not submitted_at:
        warnings.append("ROE status is submitted but submitted_at is missing.")
    if roe_status == "submitted" and not (submission_reference or "").strip():
        warnings.append(
            "ROE status is submitted but submission reference is missing."
        )
    return warnings


def _validate_roe_payload(row) -> tuple[list[str], list[str], dict]:
    payload = _row_to_payload(row)
    errors = []
    errors.extend(_validate_identity(payload))
    errors.extend(_validate_dates(payload))
    errors.extend(_validate_reason(payload))
    errors.extend(_validate_insurable(payload))
    warnings = _build_submission_warnings(payload)
    return errors, warnings, payload


def _ensure_roe_columns(conn):
    cur = conn.cursor()
    try:
        cur.execute(
            "ALTER TABLE employee_roe_records ADD COLUMN IF NOT EXISTS"
            "reason_description TEXT"
        )
        cur.execute(
            "ALTER TABLE employee_roe_records ADD COLUMN IF NOT EXISTS"
            "roe_status TEXT DEFAULT 'draft'"
        )
        cur.execute(
            "ALTER TABLE employee_roe_records ADD COLUMN IF NOT EXISTS"
            "submitted_at TIMESTAMP"
        )
        cur.execute(
            "ALTER TABLE employee_roe_records ADD COLUMN IF NOT EXISTS"
            "submitted_by TEXT"
        )
        cur.execute(
            "ALTER TABLE employee_roe_records ADD COLUMN IF NOT EXISTS"
            "submission_reference TEXT"
        )
        conn.commit()
    finally:
        cur.close()


def _service_actor() -> AuditEventActor:
    return AuditEventActor(
        actor_type="service",
        user_id=None,
        username="continuous_employment_api",
        role="service",
    )


@router.get("/roe")
async def list_roe_records(conn: Annotated[object, Depends(get_connection)]):
    _ensure_roe_columns(conn)
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT
                id AS roe_id,
                roe_number,
                employee_id,
                employee_name,
                COALESCE(reason_description, '') AS reason_description,
                reason_code,
                termination_date,
                last_day_worked AS last_day_paid,
                COALESCE(insurable_hours, 0) AS total_insurable_hours,
                COALESCE(insurable_earnings, 0) AS total_insurable_earnings,
                COALESCE(roe_status, 'draft') AS roe_status,
                created_at,
                submitted_at,
                submission_reference
            FROM employee_roe_records
            ORDER BY created_at DESC, id DESC
            """)
        rows = cur.fetchall()
        out = []
        for r in rows:
            out.append(
                {
                    "roe_id": r[0],
                    "roe_number": r[1],
                    "employee_id": r[2],
                    "employee_name": r[3],
                    "reason_description": r[4],
                    "reason_code": r[5],
                    "termination_date": r[6].isoformat() if r[6] else None,
                    "last_day_paid": r[7].isoformat() if r[7] else None,
                    "total_insurable_hours": float(r[8] or 0),
                    "total_insurable_earnings": float(r[9] or 0),
                    "roe_status": r[10] or "draft",
                    "created_at": r[11].isoformat() if r[11] else None,
                    "submitted_at": r[12].isoformat() if r[12] else None,
                    "submission_reference": r[13],
                }
            )
        return out
    finally:
        cur.close()


@router.get(
    "/roe/{roe_id}", responses={404: {"description": "ROE record not found"}}
)
async def get_roe_record(
    roe_id: int, conn: Annotated[object, Depends(get_connection)]
):
    _ensure_roe_columns(conn)
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT
                id,
                roe_number,
                employee_id,
                employee_name,
                termination_date,
                last_day_worked,
                reason_code,
                COALESCE(reason_description, ''),
                COALESCE(insurable_earnings, 0),
                COALESCE(insurable_hours, 0),
                COALESCE(roe_status, 'draft'),
                created_at,
                submitted_at,
                submitted_by,
                submission_reference,
                source_file
            FROM employee_roe_records
            WHERE id = %s
            """,
            (roe_id,),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=ROE_NOT_FOUND)
        return {
            "roe_id": row[0],
            "roe_number": row[1],
            "employee_id": row[2],
            "employee_name": row[3],
            "termination_date": row[4].isoformat() if row[4] else None,
            "last_day_paid": row[5].isoformat() if row[5] else None,
            "reason_code": row[6],
            "reason_description": row[7],
            "total_insurable_earnings": float(row[8] or 0),
            "total_insurable_hours": float(row[9] or 0),
            "roe_status": row[10],
            "created_at": row[11].isoformat() if row[11] else None,
            "submitted_at": row[12].isoformat() if row[12] else None,
            "submitted_by": row[13],
            "submission_reference": row[14],
            "source_file": row[15],
        }
    finally:
        cur.close()


@router.get(
    "/roe/{roe_id}/readiness",
    responses={404: {"description": "ROE record not found"}},
)
async def get_roe_readiness(
    roe_id: int, conn: Annotated[object, Depends(get_connection)]
):
    """Return strict ROE readiness status and actionable validation"
    "messages."""

    _ensure_roe_columns(conn)
    cur = conn.cursor()
    try:
        row = _load_roe_row(cur, roe_id)
        if not row:
            raise HTTPException(status_code=404, detail=ROE_NOT_FOUND)

        errors, warnings, payload = _validate_roe_payload(row)
        return {
            "roe_id": roe_id,
            "is_ready": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "record": payload,
        }
    finally:
        cur.close()


@router.get(
    "/roe/{roe_id}/submission-package",
    responses={404: {"description": "ROE record not found"}},
)
async def export_roe_submission_package(
    roe_id: int, conn: Annotated[object, Depends(get_connection)]
):
    """Export an ROE submission package payload for downstream ROE Web filing"
    "workflows."""

    _ensure_roe_columns(conn)
    cur = conn.cursor()
    try:
        row = _load_roe_row(cur, roe_id)
        if not row:
            raise HTTPException(status_code=404, detail=ROE_NOT_FOUND)

        errors, warnings, payload = _validate_roe_payload(row)
        package = {
            "schema_version": "roe-submission-package-v1",
            "generated_at": datetime.now().isoformat(),
            "is_ready": len(errors) == 0,
            "validation_errors": errors,
            "validation_warnings": warnings,
            "submission_channel": "service_canada_roe_web_manual_upload",
            "record": payload,
        }

        filename = f"roe_submission_package_{payload['roe_id']}.json"
        return Response(
            content=json.dumps(package, indent=2),
            media_type="application/json",
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            },
        )
    finally:
        cur.close()


@router.post(
    "/roe/create-for-any-employee",
    responses={
        404: {"description": "Employee not found"},
        500: {"description": "Failed to create ROE"},
    },
)
async def create_roe_record(
    payload: ROECreateRequest, conn: Annotated[object, Depends(get_connection)]
):
    _ensure_roe_columns(conn)
    cur = conn.cursor()
    try:
        ensure_audit_storage(conn)
        cur.execute(
            "SELECT full_name FROM employees WHERE employee_id = %s",
            (payload.employee_id,),
        )
        emp = cur.fetchone()
        if not emp:
            raise HTTPException(status_code=404, detail="Employee not found")

        employee_name = emp[0] or f"EMPLOYEE {payload.employee_id}"

        # Use payroll aggregates when available.
        cur.execute(
            """
            SELECT
                COALESCE(SUM(COALESCE(gross_pay, 0)), 0),
                COALESCE(SUM(COALESCE(hours, 0)), 0)
            FROM driver_payroll
            WHERE employee_id = %s
              AND EXTRACT(YEAR FROM COALESCE(charter_date, created_at,
              NOW())) = %s
            """,
            (payload.employee_id, payload.termination_date.year),
        )
        sums = cur.fetchone() or (0, 0)
        insurable_earnings = float(sums[0] or 0)
        insurable_hours = float(sums[1] or 0)

        cur.execute(
            """
            INSERT INTO employee_roe_records (
                employee_id, employee_name, termination_date, last_day_worked,
                reason_code, reason_description, insurable_earnings,
                insurable_hours,
                pay_period_type, source_file, created_at, roe_status
            ) VALUES (
                %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s, NOW(), %s
            )
            RETURNING id
            """,
            (
                payload.employee_id,
                employee_name,
                payload.termination_date,
                payload.termination_date,
                (payload.reason_code or "K").strip().upper()[:2],
                (payload.reason_description or "").strip() or None,
                insurable_earnings,
                insurable_hours,
                "biweekly",
                "continuous_employment_ui",
                "completed",
            ),
        )
        roe_id = int(cur.fetchone()[0])
        roe_number = f"ROE-{payload.termination_date.year}-{roe_id:06d}"

        cur.execute(
            "UPDATE employee_roe_records SET roe_number = %s WHERE id = %s",
            (roe_number, roe_id),
        )

        record_audit_event(
            conn,
            AuditEvent(
                module="continuous_employment",
                entity_type="roe_record",
                entity_id=str(roe_id),
                action="roe_created",
                source="api",
                correlation_id=None,
                actor=_service_actor(),
                before=None,
                after={
                    "employee_id": payload.employee_id,
                    "termination_date": payload.termination_date.isoformat(),
                    "reason_code": (payload.reason_code or "K").strip().upper(),
                    "roe_number": roe_number,
                },
                evidence_links=[f"employee_roe_records:{roe_id}"],
                retention_until=date(date.today().year + 6, 12, 31),
                note="ROE created",
            ),
            ensure_storage=False,
            commit=False,
        )
        conn.commit()

        return {
            "success": True,
            "roe_id": roe_id,
            "roe_number": roe_number,
            "employee_name": employee_name,
        }
    except HTTPException:
        conn.rollback()
        raise
    except Exception as exc:
        conn.rollback()
        raise HTTPException(  # noqa: B904
            status_code=500, detail=f"Failed to create ROE: {exc}"
        )
    finally:
        cur.close()


@router.post(
    "/roe/{roe_id}/submit",
    responses={
        400: {"description": "ROE is not submission-ready"},
        404: {"description": "ROE record not found"},
        500: {"description": "Failed to submit ROE"},
    },
)
async def submit_roe_record(
    roe_id: int,
    payload: ROESubmitRequest,
    conn: Annotated[object, Depends(get_connection)],
):
    _ensure_roe_columns(conn)
    cur = conn.cursor()
    try:
        ensure_audit_storage(conn)
        row = _load_roe_row(cur, roe_id)
        if not row:
            raise HTTPException(status_code=404, detail=ROE_NOT_FOUND)

        errors, warnings, _record = _validate_roe_payload(row)
        if errors:
            raise HTTPException(
                status_code=400,
                detail={
                    "message": "ROE is not submission-ready",
                    "errors": errors,
                    "warnings": warnings,
                },
            )

        sub_ref = (
            payload.submission_reference or ""
        ).strip() or f"ROE-{roe_id}-{datetime.now().strftime('%Y%m%d%H%M')}"
        extra_notes = (payload.notes or "").strip()

        if extra_notes:
            cur.execute(
                """
                UPDATE employee_roe_records
                SET roe_status = 'submitted',
                    submitted_at = NOW(),
                    submitted_by = %s,
                    submission_reference = %s,
                    source_file = COALESCE(source_file, '') || %s
                WHERE id = %s
                """,
                (
                    (payload.submitted_by or "web_app").strip(),
                    sub_ref,
                    f"\nSUBMIT_NOTE: {extra_notes}",
                    roe_id,
                ),
            )
        else:
            cur.execute(
                """
                UPDATE employee_roe_records
                SET roe_status = 'submitted',
                    submitted_at = NOW(),
                    submitted_by = %s,
                    submission_reference = %s
                WHERE id = %s
                """,
                ((payload.submitted_by or "web_app").strip(), sub_ref, roe_id),
            )

        record_audit_event(
            conn,
            AuditEvent(
                module="continuous_employment",
                entity_type="roe_record",
                entity_id=str(roe_id),
                action="roe_submitted",
                source="api",
                correlation_id=None,
                actor=_service_actor(),
                before={"roe_status": row[10] if row else None},
                after={
                    "roe_status": "submitted",
                    "submission_reference": sub_ref,
                    "submitted_by": (payload.submitted_by or "web_app").strip(),
                },
                evidence_links=[f"employee_roe_records:{roe_id}"],
                retention_until=date(date.today().year + 6, 12, 31),
                note="ROE submitted",
            ),
            ensure_storage=False,
            commit=False,
        )
        conn.commit()
        return {
            "success": True,
            "roe_id": roe_id,
            "submission_reference": sub_ref,
            "message": "ROE marked as submitted with audit metadata.",
        }
    except HTTPException:
        conn.rollback()
        raise
    except Exception as exc:
        conn.rollback()
        raise HTTPException(  # noqa: B904
            status_code=500, detail=f"Failed to submit ROE: {exc}"
        )
    finally:
        cur.close()
