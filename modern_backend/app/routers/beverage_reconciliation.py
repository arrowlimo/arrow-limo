from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from ..audit.engine import ensure_audit_storage, record_audit_event
from ..audit.schemas import AuditEvent, AuditEventActor
from ..db import get_connection

router = APIRouter(prefix="/api/beverage", tags=["beverage-reconciliation"])


class BeverageReconciliationUpsert(BaseModel):
    date: date
    period: str = Field(min_length=1, max_length=120)
    expected_count: int
    actual_count: int
    notes: str | None = Field(default=None, max_length=1000)


def _ensure_table(conn):
    cur = conn.cursor()
    try:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS beverage_reconciliations (
                id SERIAL PRIMARY KEY,
                reconciliation_date DATE NOT NULL,
                period TEXT NOT NULL,
                expected_count INTEGER NOT NULL,
                actual_count INTEGER NOT NULL,
                notes TEXT,
                created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMP NOT NULL DEFAULT NOW()
            )
            """
        )
        conn.commit()
    finally:
        cur.close()


def _status_from_variance(variance: int) -> str:
    if variance == 0:
        return "reconciled"
    return "variance"


def _audit_actor(request: Request) -> AuditEventActor:
    user = getattr(request.state, "current_user", None) or {}
    return AuditEventActor(
        actor_type="user" if user else "service",
        user_id=str(user.get("user_id") or user.get("employee_id") or "") or None,
        username=user.get("username") or user.get("name"),
        role=user.get("role"),
    )


@router.get("/reconciliations")
def list_reconciliations(
    date: str | None = Query(default=None),
    status: str | None = Query(default=None),
    conn=Depends(get_connection),
):
    _ensure_table(conn)
    cur = conn.cursor()
    try:
        sql = """
            SELECT id, reconciliation_date, period,
                   expected_count, actual_count, notes
            FROM beverage_reconciliations
            WHERE 1=1
        """
        params: list[object] = []
        if date:
            sql += " AND reconciliation_date = %s"
            params.append(date)
        sql += " ORDER BY reconciliation_date DESC, id DESC"
        cur.execute(sql, params)
        rows = cur.fetchall()

        out = []
        for row in rows:
            variance = int((row[4] or 0) - (row[3] or 0))
            rec_status = _status_from_variance(variance)
            if status and status != rec_status:
                continue
            out.append(
                {
                    "id": int(row[0]),
                    "date": row[1].isoformat() if row[1] else None,
                    "period": row[2],
                    "expected_count": int(row[3] or 0),
                    "actual_count": int(row[4] or 0),
                    "variance": variance,
                    "status": rec_status,
                    "notes": row[5] or "",
                }
            )
        return out
    finally:
        cur.close()


@router.post("/reconciliations")
def create_reconciliation(
    payload: BeverageReconciliationUpsert,
    request: Request,
    conn=Depends(get_connection),
):
    _ensure_table(conn)
    cur = conn.cursor()
    try:
        ensure_audit_storage(conn)
        cur.execute(
            """
            INSERT INTO beverage_reconciliations (
                reconciliation_date, period, expected_count, actual_count, notes
            )
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                payload.date,
                payload.period.strip(),
                payload.expected_count,
                payload.actual_count,
                payload.notes.strip() if payload.notes else None,
            ),
        )
        row = cur.fetchone()

        event = AuditEvent(
            module="beverage_reconciliation",
            entity_type="beverage_reconciliation",
            entity_id=str(int(row[0])),
            action="beverage_reconciliation_created",
            source="api",
            correlation_id=request.headers.get("X-Request-ID"),
            actor=_audit_actor(request),
            before=None,
            after={
                "date": payload.date.isoformat(),
                "period": payload.period.strip(),
                "expected_count": payload.expected_count,
                "actual_count": payload.actual_count,
                "notes": payload.notes,
            },
            evidence_links=[f"beverage_reconciliations:{int(row[0])}"],
            retention_until=date(date.today().year + 6, 12, 31),
            note="Beverage reconciliation create audit record",
        )
        record_audit_event(conn, event, ensure_storage=False, commit=False)

        conn.commit()
        return {"status": "created", "id": int(row[0])}
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=400, detail=f"create_failed: {exc}") from exc
    finally:
        cur.close()


@router.put("/reconciliations/{reconciliation_id}")
def update_reconciliation(
    reconciliation_id: int,
    payload: BeverageReconciliationUpsert,
    request: Request,
    conn=Depends(get_connection),
):
    _ensure_table(conn)
    cur = conn.cursor()
    try:
        ensure_audit_storage(conn)
        cur.execute(
            """
            SELECT reconciliation_date, period, expected_count, actual_count, notes
            FROM beverage_reconciliations
            WHERE id = %s
            """,
            (reconciliation_id,),
        )
        before = cur.fetchone()
        if not before:
            raise HTTPException(status_code=404, detail="reconciliation_not_found")

        cur.execute(
            """
            UPDATE beverage_reconciliations
            SET reconciliation_date = %s,
                period = %s,
                expected_count = %s,
                actual_count = %s,
                notes = %s,
                updated_at = NOW()
            WHERE id = %s
            """,
            (
                payload.date,
                payload.period.strip(),
                payload.expected_count,
                payload.actual_count,
                payload.notes.strip() if payload.notes else None,
                reconciliation_id,
            ),
        )

        event = AuditEvent(
            module="beverage_reconciliation",
            entity_type="beverage_reconciliation",
            entity_id=str(reconciliation_id),
            action="beverage_reconciliation_updated",
            source="api",
            correlation_id=request.headers.get("X-Request-ID"),
            actor=_audit_actor(request),
            before={
                "date": before[0].isoformat() if before[0] else None,
                "period": before[1],
                "expected_count": int(before[2] or 0),
                "actual_count": int(before[3] or 0),
                "notes": before[4],
            },
            after={
                "date": payload.date.isoformat(),
                "period": payload.period.strip(),
                "expected_count": payload.expected_count,
                "actual_count": payload.actual_count,
                "notes": payload.notes,
            },
            evidence_links=[f"beverage_reconciliations:{reconciliation_id}"],
            retention_until=date(date.today().year + 6, 12, 31),
            note="Beverage reconciliation update audit record",
        )
        record_audit_event(conn, event, ensure_storage=False, commit=False)

        conn.commit()
        return {"status": "updated", "id": reconciliation_id}
    except HTTPException:
        conn.rollback()
        raise
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=400, detail=f"update_failed: {exc}") from exc
    finally:
        cur.close()
