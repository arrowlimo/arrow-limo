"""
T1 Personal Tax Return API Router.

Provides a line-item return store for owner/personal tax entry and
submission tracking.
"""

from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from ..audit.engine import ensure_audit_storage, record_audit_event
from ..audit.schemas import AuditEvent, AuditEventActor
from ..db import get_connection

router = APIRouter(prefix="/api/t1", tags=["T1 Personal Tax"])


class T1LineItem(BaseModel):
    line_number: str = Field(min_length=1, max_length=20)
    line_description: str = Field(min_length=1, max_length=200)
    amount: float = 0.0
    notes: str | None = None


class T1ReturnCreate(BaseModel):
    tax_year: int = Field(ge=2000, le=2100)
    taxpayer_name: str = Field(min_length=1, max_length=200)
    sin: str | None = Field(default=None, max_length=20)
    notes: str | None = Field(default=None, max_length=1000)


class T1SubmitRequest(BaseModel):
    submitted_by: str = "web_app"
    submission_reference: str | None = None
    notes: str | None = None
    total_tax: float | None = None
    refund_owing: float | None = None


def _audit_actor(request: Request) -> AuditEventActor:
    user = getattr(request.state, "current_user", None) or {}
    return AuditEventActor(
        actor_type="user" if user else "service",
        user_id=str(user.get("user_id") or user.get("employee_id") or "") or None,
        username=user.get("username") or user.get("name"),
        role=user.get("role"),
    )


def _ensure_tables(conn) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS t1_return_metadata (
                return_id SERIAL PRIMARY KEY,
                tax_year INTEGER UNIQUE NOT NULL,
                taxpayer_name TEXT NOT NULL,
                sin TEXT,
                status TEXT NOT NULL DEFAULT 'draft',
                total_income NUMERIC,
                total_tax NUMERIC,
                refund_owing NUMERIC,
                submission_reference TEXT,
                submitted_by TEXT,
                submitted_at TIMESTAMPTZ,
                notes TEXT,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS t1_return_lines (
                line_id SERIAL PRIMARY KEY,
                return_id INTEGER NOT NULL REFERENCES t1_return_metadata(return_id)
                    ON DELETE CASCADE,
                line_number TEXT NOT NULL,
                line_description TEXT NOT NULL,
                amount NUMERIC NOT NULL DEFAULT 0,
                notes TEXT,
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                UNIQUE(return_id, line_number)
            )
            """
        )
    conn.commit()


def _load_return(conn, tax_year: int) -> dict | None:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT return_id, tax_year, taxpayer_name, sin, status,
                   total_income, total_tax, refund_owing,
                   submission_reference, submitted_by, submitted_at,
                   notes, created_at, updated_at
            FROM t1_return_metadata
            WHERE tax_year = %s
            """,
            (tax_year,),
        )
        row = cur.fetchone()
        if not row:
            return None

        cur.execute(
            """
            SELECT line_number, line_description, amount, notes
            FROM t1_return_lines
            WHERE return_id = %s
            ORDER BY line_number
            """,
            (row[0],),
        )
        lines = [
            {
                "line_number": r[0],
                "line_description": r[1],
                "amount": float(r[2] or 0),
                "notes": r[3],
            }
            for r in cur.fetchall()
        ]

    return {
        "return_id": row[0],
        "tax_year": row[1],
        "taxpayer_name": row[2],
        "sin": row[3],
        "status": row[4],
        "total_income": float(row[5]) if row[5] is not None else None,
        "total_tax": float(row[6]) if row[6] is not None else None,
        "refund_owing": float(row[7]) if row[7] is not None else None,
        "submission_reference": row[8],
        "submitted_by": row[9],
        "submitted_at": row[10].isoformat() if row[10] else None,
        "notes": row[11],
        "created_at": row[12].isoformat() if row[12] else None,
        "updated_at": row[13].isoformat() if row[13] else None,
        "lines": lines,
    }


@router.post("/returns")
async def create_t1_return(payload: T1ReturnCreate, request: Request, conn=Depends(get_connection)):
    _ensure_tables(conn)
    ensure_audit_storage(conn)
    cur = conn.cursor()
    try:
        cur.execute("SELECT return_id FROM t1_return_metadata WHERE tax_year = %s", (payload.tax_year,))
        if cur.fetchone():
            raise HTTPException(status_code=400, detail="T1 return already exists")

        cur.execute(
            """
            INSERT INTO t1_return_metadata (
                tax_year, taxpayer_name, sin, notes, status, created_at, updated_at
            )
            VALUES (%s, %s, %s, %s, 'draft', NOW(), NOW())
            RETURNING return_id
            """,
            (payload.tax_year, payload.taxpayer_name.strip(), payload.sin, payload.notes),
        )
        row = cur.fetchone()
        record_audit_event(
            conn,
            AuditEvent(
                module="t1_returns",
                entity_type="t1_return",
                entity_id=str(row[0]),
                action="t1_return_created",
                source="api",
                correlation_id=request.headers.get("X-Request-ID"),
                actor=_audit_actor(request),
                before=None,
                after={
                    "tax_year": payload.tax_year,
                    "taxpayer_name": payload.taxpayer_name,
                    "sin": payload.sin,
                },
                evidence_links=[f"t1_return_metadata:{row[0]}"],
                retention_until=date(date.today().year + 6, 12, 31),
                note="T1 return created",
            ),
            ensure_storage=False,
            commit=False,
        )
        conn.commit()
        return _load_return(conn, payload.tax_year)
    except HTTPException:
        conn.rollback()
        raise
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        cur.close()


@router.get("/returns/{tax_year}")
async def get_t1_return(tax_year: int, conn=Depends(get_connection)):
    _ensure_tables(conn)
    return _load_return(conn, tax_year)


@router.post("/returns/{return_id}/lines")
async def save_t1_lines(return_id: int, payload: list[T1LineItem], request: Request, conn=Depends(get_connection)):
    _ensure_tables(conn)
    ensure_audit_storage(conn)
    cur = conn.cursor()
    try:
        cur.execute("SELECT tax_year FROM t1_return_metadata WHERE return_id = %s", (return_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="T1 return not found")

        for line in payload:
            cur.execute(
                """
                INSERT INTO t1_return_lines (
                    return_id, line_number, line_description, amount, notes, updated_at
                )
                VALUES (%s, %s, %s, %s, %s, NOW())
                ON CONFLICT (return_id, line_number)
                DO UPDATE SET
                    line_description = EXCLUDED.line_description,
                    amount = EXCLUDED.amount,
                    notes = EXCLUDED.notes,
                    updated_at = NOW()
                """,
                (return_id, line.line_number.strip(), line.line_description.strip(), line.amount, line.notes),
            )

        cur.execute(
            """
            UPDATE t1_return_metadata
            SET updated_at = NOW()
            WHERE return_id = %s
            """,
            (return_id,),
        )
        record_audit_event(
            conn,
            AuditEvent(
                module="t1_returns",
                entity_type="t1_return",
                entity_id=str(return_id),
                action="t1_lines_saved",
                source="api",
                correlation_id=request.headers.get("X-Request-ID"),
                actor=_audit_actor(request),
                before=None,
                after={"return_id": return_id, "line_count": len(payload)},
                evidence_links=[f"t1_return_lines:{return_id}"],
                retention_until=date(date.today().year + 6, 12, 31),
                note="T1 line items saved",
            ),
            ensure_storage=False,
            commit=False,
        )
        conn.commit()
        return _load_return(conn, int(row[0]))
    except HTTPException:
        conn.rollback()
        raise
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        cur.close()


@router.post("/returns/{return_id}/submit")
async def submit_t1_return(return_id: int, payload: T1SubmitRequest, request: Request, conn=Depends(get_connection)):
    _ensure_tables(conn)
    ensure_audit_storage(conn)
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT tax_year, status FROM t1_return_metadata WHERE return_id = %s",
            (return_id,),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="T1 return not found")

        cur.execute(
            """
            UPDATE t1_return_metadata
            SET status = 'submitted',
                total_tax = COALESCE(%s, total_tax),
                refund_owing = COALESCE(%s, refund_owing),
                submission_reference = %s,
                submitted_by = %s,
                submitted_at = NOW(),
                notes = CASE
                    WHEN %s IS NULL OR %s = '' THEN notes
                    WHEN notes IS NULL OR notes = '' THEN %s
                    ELSE notes || E'\n' || %s
                END,
                updated_at = NOW()
            WHERE return_id = %s
            """,
            (
                payload.total_tax,
                payload.refund_owing,
                (payload.submission_reference or "").strip() or f"T1-{row[0]}",
                (payload.submitted_by or "web_app").strip(),
                payload.notes,
                payload.notes,
                payload.notes,
                payload.notes,
                return_id,
            ),
        )

        record_audit_event(
            conn,
            AuditEvent(
                module="t1_returns",
                entity_type="t1_return",
                entity_id=str(return_id),
                action="t1_return_submitted",
                source="api",
                correlation_id=request.headers.get("X-Request-ID"),
                actor=_audit_actor(request),
                before={"status": row[1]},
                after={
                    "status": "submitted",
                    "submission_reference": (payload.submission_reference or "").strip() or f"T1-{row[0]}",
                },
                evidence_links=[f"t1_return_metadata:{return_id}"],
                retention_until=date(date.today().year + 6, 12, 31),
                note="T1 return submitted",
            ),
            ensure_storage=False,
            commit=False,
        )
        conn.commit()
        return _load_return(conn, int(row[0]))
    except HTTPException:
        conn.rollback()
        raise
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        cur.close()
