"""Driver self-service compliance records with admin-approval workflow.

Drivers view and edit their own licence, permit, certification and contact
records here, but nothing reaches the live employees table directly. Every
edit is queued as a change request that keeps the old value beside the new
value until an administrator authorizes it in the PC app.
"""

import base64
import json
from datetime import date, datetime

import psycopg2
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..auth import get_current_user
from ..db import get_connection, return_connection

router = APIRouter(prefix="/api/chauffeur", tags=["driver_records"])

MAX_UPLOAD_BYTES = 8 * 1024 * 1024

ALLOWED_MIME_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
    "image/heic",
    "image/webp",
}

# Only these employee columns may be changed from the driver portal. Pay
# rates, employment status, hire date and SIN are deliberately excluded so a
# driver can never grant themselves a raise or alter employment terms.
EDITABLE_FIELDS: dict[str, dict[str, str]] = {
    "driver_license_number": {"label": "Driver Licence Number", "type": "text"},
    "driver_license_class": {"label": "Driver Licence Class", "type": "text"},
    "driver_license_expiry": {"label": "Driver Licence Expiry", "type": "date"},
    "chauffeur_permit_number": {
        "label": "Driver-for-Hire / Chauffeur Permit Number",
        "type": "text",
    },
    "chauffeur_permit_expiry": {
        "label": "Driver-for-Hire / Chauffeur Permit Expiry",
        "type": "date",
    },
    "proserve_number": {"label": "ProServe Certificate Number", "type": "text"},
    "proserve_expiry": {"label": "ProServe Expiry", "type": "date"},
    "medical_fitness_expiry": {"label": "Medical Fitness Expiry", "type": "date"},
    "drivers_abstract_date": {"label": "Driver Abstract Date", "type": "date"},
    "vulnerable_sector_check_date": {
        "label": "Vulnerable Sector Check Date",
        "type": "date",
    },
    "phone": {"label": "Phone", "type": "text"},
    "cell_phone": {"label": "Cell Phone", "type": "text"},
    "email": {"label": "Email", "type": "text"},
    "street_address": {"label": "Street Address", "type": "text"},
    "city": {"label": "City", "type": "text"},
    "province": {"label": "Province", "type": "text"},
    "postal_code": {"label": "Postal Code", "type": "text"},
    "emergency_contact_name": {"label": "Emergency Contact Name", "type": "text"},
    "emergency_contact_phone": {"label": "Emergency Contact Phone", "type": "text"},
}

DOCUMENT_TYPES = {
    "DRIVER_LICENCE",
    "CHAUFFEUR_PERMIT",
    "PROSERVE",
    "MEDICAL",
    "DRIVER_ABSTRACT",
    "VULNERABLE_SECTOR",
    "TRAINING",
    "OTHER",
}


class ChangeRequestItem(BaseModel):
    field_key: str = Field(min_length=1, max_length=100)
    new_value: str | None = Field(default=None, max_length=500)


class ChangeRequestSubmission(BaseModel):
    changes: list[ChangeRequestItem] = Field(min_length=1, max_length=40)


class DocumentUpload(BaseModel):
    document_type: str = Field(min_length=1, max_length=60)
    document_name: str = Field(min_length=1, max_length=255)
    mime_type: str = Field(min_length=1, max_length=100)
    file_base64: str = Field(min_length=1)
    issued_date: date | None = None
    expiry_date: date | None = None
    document_number: str | None = Field(default=None, max_length=100)
    notes: str | None = Field(default=None, max_length=2000)


# Statuses a driver may claim for themselves. "completed" is deliberately
# allowed only as a *request* — it becomes real once an administrator
# authorizes it in the PC app, so no driver can self-certify their own
# compliance.
TRAINING_STATUSES = {"not_started", "in_progress", "completed"}


class TrainingSubmission(BaseModel):
    program_id: int
    status: str = Field(min_length=1, max_length=30)
    started_date: date | None = None
    completed_date: date | None = None
    trainer_name: str | None = Field(default=None, max_length=120)
    score: float | None = Field(default=None, ge=0, le=100)
    notes: str | None = Field(default=None, max_length=2000)



def _employee_id_from_user(user: dict) -> int:
    employee_id = user.get("employee_id")
    if employee_id is None:
        raise HTTPException(status_code=403, detail="Employee context required")
    try:
        return int(employee_id)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=403, detail="Invalid employee context") from exc


def _display_value(value) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def _normalise_submitted_value(field_key: str, raw_value: str | None) -> str | None:
    value = (raw_value or "").strip()
    if not value:
        return None
    if EDITABLE_FIELDS[field_key]["type"] == "date":
        try:
            return date.fromisoformat(value).isoformat()
        except ValueError as exc:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"{EDITABLE_FIELDS[field_key]['label']} must be a valid "
                    "date in YYYY-MM-DD format"
                ),
            ) from exc
    return value


@router.get("/me/compliance")
def get_my_compliance_records(current_user: dict = Depends(get_current_user)):
    """Return live compliance values plus anything awaiting admin approval."""
    employee_id = _employee_id_from_user(current_user)
    columns = ", ".join(EDITABLE_FIELDS.keys())
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT {columns} FROM employees WHERE employee_id = %s",  # nosec
                (employee_id,),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Employee record not found")
            live_values = dict(zip(EDITABLE_FIELDS.keys(), row, strict=False))

            cur.execute(
                """
                SELECT request_id, field_key, field_label, old_value,
                       new_value, submitted_at
                FROM employee_change_requests
                WHERE employee_id = %s AND status = 'PENDING'
                ORDER BY submitted_at DESC, request_id DESC
                """,
                (employee_id,),
            )
            pending_rows = cur.fetchall()

            cur.execute(
                """
                SELECT upload_id, document_type, document_name, mime_type,
                       file_size, issued_date, expiry_date, document_number,
                       status, uploaded_at
                FROM employee_document_uploads
                WHERE employee_id = %s
                ORDER BY uploaded_at DESC
                LIMIT 100
                """,
                (employee_id,),
            )
            document_rows = cur.fetchall()

        pending_by_field = {row[1]: row for row in pending_rows}
        fields = []
        for field_key, meta in EDITABLE_FIELDS.items():
            pending = pending_by_field.get(field_key)
            fields.append(
                {
                    "field_key": field_key,
                    "label": meta["label"],
                    "type": meta["type"],
                    "current_value": _display_value(live_values.get(field_key)),
                    "pending_value": pending[4] if pending else None,
                    "pending_since": (
                        pending[5].isoformat() if pending and pending[5] else None
                    ),
                    "awaiting_approval": pending is not None,
                }
            )

        return {
            "fields": fields,
            "pending_count": len(pending_rows),
            "documents": [
                {
                    "upload_id": doc[0],
                    "document_type": doc[1],
                    "document_name": doc[2],
                    "mime_type": doc[3],
                    "file_size": doc[4],
                    "issued_date": doc[5].isoformat() if doc[5] else None,
                    "expiry_date": doc[6].isoformat() if doc[6] else None,
                    "document_number": doc[7],
                    "status": doc[8],
                    "uploaded_at": doc[9].isoformat() if doc[9] else None,
                }
                for doc in document_rows
            ],
        }
    finally:
        return_connection(conn)


@router.get("/me/training")
def get_my_training_checklist(current_user: dict = Depends(get_current_user)):
    """This driver's training checklist, with any pending change requests.

    Progress shown here is what the office has verified. Anything the driver
    has submitted but that is not yet authorized appears separately as
    ``pending`` so they can see it is awaiting review rather than live.
    """
    employee_id = _employee_id_from_user(current_user)
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT step_number, category, program_name, is_mandatory,
                       effective_status, started_date, completed_date,
                       expiry_date, days_until_expiry, program_id
                FROM v_employee_training_status
                WHERE employee_id = %s
                ORDER BY step_number
                """,
                (employee_id,),
            )
            program_rows = cur.fetchall()

            cur.execute(
                """
                SELECT i.program_id, i.item_name, i.is_required,
                       COALESCE(p.completed, FALSE), p.completed_date
                FROM training_checklist_items i
                LEFT JOIN employee_checklist_progress p
                       ON p.item_id = i.item_id
                      AND p.employee_id = %s
                ORDER BY i.program_id, i.sort_order, i.item_id
                """,
                (employee_id,),
            )
            item_rows = cur.fetchall()

            cur.execute(
                """
                SELECT field_key, new_value, submitted_at
                  FROM employee_change_requests
                 WHERE employee_id = %s
                   AND status = 'PENDING'
                   AND field_key LIKE 'training:%%'
                """,
                (employee_id,),
            )
            pending_rows = cur.fetchall()

        pending_by_program: dict[int, dict] = {}
        for field_key, raw_value, submitted_at in pending_rows:
            try:
                pending_program_id = int(str(field_key).split(":", 1)[1])
                proposed = json.loads(raw_value or "")
            except (IndexError, ValueError, TypeError):
                continue
            if not isinstance(proposed, dict):
                continue
            pending_by_program[pending_program_id] = {
                "summary": _summarise_training(proposed),
                "is_removal": bool(proposed.get("_removed")),
                "submitted_at": (
                    submitted_at.isoformat() if submitted_at else None
                ),
            }

        items_by_program: dict[int, list] = {}
        for program_id, name, required, completed, completed_date in item_rows:
            items_by_program.setdefault(program_id, []).append(
                {
                    "item_name": name,
                    "is_required": bool(required),
                    "completed": bool(completed),
                    "completed_date": (
                        completed_date.isoformat() if completed_date else None
                    ),
                }
            )

        programs = []
        counts = {"completed": 0, "in_progress": 0, "expired": 0, "not_started": 0}
        for row in program_rows:
            status = row[4] or "not_started"
            if status in counts:
                counts[status] += 1
            programs.append(
                {
                    "step_number": row[0],
                    "program_id": row[9],
                    "category": row[1],
                    "program_name": row[2],
                    "is_mandatory": bool(row[3]),
                    "status": status,
                    "started_date": row[5].isoformat() if row[5] else None,
                    "completed_date": row[6].isoformat() if row[6] else None,
                    "expiry_date": row[7].isoformat() if row[7] else None,
                    "days_until_expiry": row[8],
                    "items": items_by_program.get(row[9], []),
                    "pending": pending_by_program.get(row[9]),
                }
            )

        return {"programs": programs, "summary": counts}
    finally:
        return_connection(conn)


def _training_field_key(program_id: int) -> str:
    return f"training:{int(program_id)}"


def _summarise_training(record: dict | None) -> str:
    """Render a training record the way a reviewer wants to read it."""
    if not record:
        return "Not on checklist"
    if record.get("_removed"):
        return "Remove from checklist"
    parts = [str(record.get("status") or "not_started").replace("_", " ")]
    if record.get("started_date"):
        parts.append(f"started {record['started_date']}")
    if record.get("completed_date"):
        parts.append(f"completed {record['completed_date']}")
    if record.get("trainer_name"):
        parts.append(f"trainer {record['trainer_name']}")
    if record.get("score") is not None:
        parts.append(f"score {record['score']}")
    return ", ".join(parts)


def _queue_training_request(cur, employee_id, user, program_id, proposed):
    """Queue one training change for administrator authorization."""
    cur.execute(
        "SELECT program_name FROM training_programs WHERE program_id = %s",
        (program_id,),
    )
    program = cur.fetchone()
    if not program:
        raise HTTPException(status_code=404, detail="Training program not found")

    cur.execute(
        """
        SELECT status, started_date, completed_date, trainer_name, score
          FROM employee_training_records
         WHERE employee_id = %s AND program_id = %s
        """,
        (employee_id, program_id),
    )
    row = cur.fetchone()
    current = None
    if row:
        current = {
            "status": row[0],
            "started_date": _display_value(row[1]) or None,
            "completed_date": _display_value(row[2]) or None,
            "trainer_name": row[3],
            "score": float(row[4]) if row[4] is not None else None,
        }

    if proposed.get("_removed") and not row:
        raise HTTPException(
            status_code=400,
            detail="That program is not on your checklist",
        )

    field_key = _training_field_key(program_id)
    cur.execute(
        """
        UPDATE employee_change_requests
        SET status = 'REJECTED',
            reviewed_by_username = 'system (superseded)',
            reviewed_at = NOW(),
            review_notes = 'Superseded by a newer driver submission'
        WHERE employee_id = %s AND field_key = %s AND status = 'PENDING'
        """,
        (employee_id, field_key),
    )
    cur.execute("SELECT nextval('employee_change_batch_seq')")
    batch_id = cur.fetchone()[0]
    cur.execute(
        """
        INSERT INTO employee_change_requests (
            batch_id, employee_id, submitted_by_user_id,
            submitted_by_username, field_key, field_label,
            old_value, new_value
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING request_id
        """,
        (
            batch_id,
            employee_id,
            user.get("user_id"),
            str(user.get("username") or ""),
            field_key,
            f"Training — {program[0]}",
            _summarise_training(current),
            json.dumps(proposed),
        ),
    )
    return {
        "request_id": cur.fetchone()[0],
        "batch_id": batch_id,
        "program": program[0],
        "old_value": _summarise_training(current),
        "new_value": _summarise_training(proposed),
    }


@router.post("/me/training", status_code=201)
def submit_training_record(
    payload: TrainingSubmission,
    current_user: dict = Depends(get_current_user),
):
    """Request that a training record be added or updated.

    The driver's checklist is not changed here. The request waits in the
    approval queue so an administrator verifies the training actually
    happened before it counts towards compliance.
    """
    employee_id = _employee_id_from_user(current_user)

    if payload.status not in TRAINING_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"Status must be one of: {', '.join(sorted(TRAINING_STATUSES))}",
        )
    if payload.status == "completed" and not payload.completed_date:
        raise HTTPException(
            status_code=400,
            detail="A completed program needs the date it was completed",
        )
    today = date.today()
    for label, value in (
        ("Completion date", payload.completed_date),
        ("Start date", payload.started_date),
    ):
        if value and value > today:
            raise HTTPException(
                status_code=400, detail=f"{label} cannot be in the future"
            )
    if (
        payload.started_date
        and payload.completed_date
        and payload.completed_date < payload.started_date
    ):
        raise HTTPException(
            status_code=400,
            detail="Completion date cannot be before the start date",
        )

    proposed = {
        "status": payload.status,
        "started_date": payload.started_date.isoformat()
        if payload.started_date
        else None,
        "completed_date": payload.completed_date.isoformat()
        if payload.completed_date
        else None,
        "trainer_name": (payload.trainer_name or "").strip() or None,
        "score": payload.score,
        "notes": (payload.notes or "").strip() or None,
    }

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            queued = _queue_training_request(
                cur, employee_id, current_user, payload.program_id, proposed
            )
        conn.commit()
        return {
            "status": "pending_approval",
            "queued": queued,
            "message": (
                "Your training update was submitted and is waiting for "
                "administrator authorization. Your checklist stays unchanged "
                "until it is approved."
            ),
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        return_connection(conn)


@router.delete("/me/training/{program_id}", status_code=201)
def request_training_removal(
    program_id: int,
    current_user: dict = Depends(get_current_user),
):
    """Request that a program be taken off this driver's checklist."""
    employee_id = _employee_id_from_user(current_user)
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            queued = _queue_training_request(
                cur, employee_id, current_user, program_id, {"_removed": True}
            )
        conn.commit()
        return {
            "status": "pending_approval",
            "queued": queued,
            "message": (
                "Your removal request was submitted and is waiting for "
                "administrator authorization."
            ),
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        return_connection(conn)


@router.post("/me/compliance", status_code=201)
def submit_compliance_changes(
    payload: ChangeRequestSubmission,
    current_user: dict = Depends(get_current_user),
):
    """Queue record changes for administrator authorization."""
    employee_id = _employee_id_from_user(current_user)
    username = str(current_user.get("username") or "")

    for item in payload.changes:
        if item.field_key not in EDITABLE_FIELDS:
            raise HTTPException(
                status_code=400,
                detail=f"Field '{item.field_key}' cannot be changed from the portal",
            )

    columns = ", ".join(EDITABLE_FIELDS.keys())
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT {columns} FROM employees WHERE employee_id = %s",  # nosec
                (employee_id,),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Employee record not found")
            live_values = dict(zip(EDITABLE_FIELDS.keys(), row, strict=False))

            cur.execute("SELECT nextval('employee_change_batch_seq')")
            batch_id = cur.fetchone()[0]

            queued = []
            for item in payload.changes:
                new_value = _normalise_submitted_value(item.field_key, item.new_value)
                old_value = _display_value(live_values.get(item.field_key))
                if (new_value or "") == old_value:
                    continue

                # Replace any superseded pending request for the same field so
                # reviewers only ever see the driver's latest intent.
                cur.execute(
                    """
                    UPDATE employee_change_requests
                    SET status = 'REJECTED',
                        reviewed_by_username = 'system (superseded)',
                        reviewed_at = NOW(),
                        review_notes = 'Superseded by a newer driver submission'
                    WHERE employee_id = %s AND field_key = %s AND status = 'PENDING'
                    """,
                    (employee_id, item.field_key),
                )
                cur.execute(
                    """
                    INSERT INTO employee_change_requests (
                        batch_id, employee_id, submitted_by_user_id,
                        submitted_by_username, field_key, field_label,
                        old_value, new_value
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING request_id
                    """,
                    (
                        batch_id,
                        employee_id,
                        current_user.get("user_id"),
                        username,
                        item.field_key,
                        EDITABLE_FIELDS[item.field_key]["label"],
                        old_value or None,
                        new_value,
                    ),
                )
                queued.append(
                    {
                        "request_id": cur.fetchone()[0],
                        "field_key": item.field_key,
                        "label": EDITABLE_FIELDS[item.field_key]["label"],
                        "old_value": old_value,
                        "new_value": new_value,
                    }
                )
        conn.commit()
        return {
            "status": "pending_approval",
            "batch_id": batch_id,
            "queued": queued,
            "message": (
                "Your changes were submitted and are waiting for administrator "
                "authorization. Your record stays unchanged until approved."
            ),
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        return_connection(conn)


@router.post("/me/documents", status_code=201)
def upload_my_document(
    payload: DocumentUpload,
    current_user: dict = Depends(get_current_user),
):
    """Store a photo or PDF of a licence, permit or certificate."""
    employee_id = _employee_id_from_user(current_user)

    document_type = payload.document_type.strip().upper()
    if document_type not in DOCUMENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Document type must be one of: {', '.join(sorted(DOCUMENT_TYPES))}",
        )

    mime_type = payload.mime_type.strip().lower()
    if mime_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=400,
            detail="Upload a PDF or a photo (JPG, PNG, HEIC or WEBP)",
        )

    raw = payload.file_base64
    if "," in raw[:64] and raw.lstrip().startswith("data:"):
        raw = raw.split(",", 1)[1]
    try:
        file_bytes = base64.b64decode(raw, validate=True)
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=400, detail="File upload was not readable") from exc

    if not file_bytes:
        raise HTTPException(status_code=400, detail="File upload was empty")
    if len(file_bytes) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=400,
            detail="File is larger than the 8 MB limit; take a smaller photo",
        )

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO employee_document_uploads (
                    employee_id, document_type, document_name, mime_type,
                    file_size, file_data, issued_date, expiry_date,
                    document_number, notes, uploaded_by_username
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING upload_id, uploaded_at
                """,
                (
                    employee_id,
                    document_type,
                    payload.document_name.strip(),
                    mime_type,
                    len(file_bytes),
                    psycopg2.Binary(file_bytes),
                    payload.issued_date,
                    payload.expiry_date,
                    (payload.document_number or "").strip() or None,
                    (payload.notes or "").strip() or None,
                    str(current_user.get("username") or ""),
                ),
            )
            upload_id, uploaded_at = cur.fetchone()
        conn.commit()
        return {
            "upload_id": upload_id,
            "status": "PENDING",
            "file_size": len(file_bytes),
            "uploaded_at": uploaded_at.isoformat() if uploaded_at else None,
            "message": (
                "Document uploaded and waiting for administrator review."
            ),
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        return_connection(conn)
