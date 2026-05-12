from datetime import date, timedelta
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from ..audit.engine import ensure_audit_storage, record_audit_event
from ..audit.schemas import AuditEvent, AuditEventActor
from ..db import cursor

router = APIRouter(prefix="/api", tags=["payments"])


def _audit_actor(request: Request | None) -> AuditEventActor:
    if request is None:
        return AuditEventActor(actor_type="system", username="system")
    username = request.headers.get("X-User-Name") or request.headers.get(
        "X-User"
    )
    role = request.headers.get("X-User-Role")
    user_id = request.headers.get("X-User-Id")
    if not username:
        username = request.headers.get("X-Forwarded-User")
    return AuditEventActor(
        actor_type="user" if username else "service",
        user_id=user_id,
        username=username,
        role=role,
    )


def _load_payment_snapshot(cur, payment_id: int) -> dict[str, Any] | None:
    cur.execute(
        """
        SELECT payment_id, charter_id, amount, payment_date,
               payment_method, payment_key, notes, created_at, last_updated
        FROM payments
        WHERE payment_id = %s
        """,
        (payment_id,),
    )
    row = cur.fetchone()
    if not row:
        return None
    cols = [d[0] for d in (cur.description or [])]
    return dict(zip(cols, row, strict=False))


class PaymentCreate(BaseModel):
    amount: float
    payment_date: str | None = None  # ISO date
    payment_method: str | None = "credit_card"
    payment_key: str | None = None
    notes: str | None = None


class PaymentUpdate(BaseModel):
    amount: float | None = None
    payment_date: str | None = None
    payment_method: str | None = None
    payment_key: str | None = None
    notes: str | None = None


@router.get("/charters/{charter_id}/payments")
def list_payments(charter_id: int) -> dict[str, Any]:
    with cursor() as cur:
        cur.execute(
            """
            SELECT payment_id, charter_id, amount, payment_date,
            payment_method, payment_key, notes, created_at, last_updated
            FROM payments
            WHERE charter_id = %s
            ORDER BY payment_date DESC, payment_id DESC
            """,
            (charter_id,),
        )
        rows = cur.fetchall()
        cols = [d[0] for d in (cur.description or [])]
        items = [dict(zip(cols, r, strict=False)) for r in rows]
    return {"payments": items}


@router.post("/charters/{charter_id}/payments", status_code=201)
def create_payment(
    charter_id: int,
    body: PaymentCreate,
    request: Request,
) -> dict[str, Any]:
    with cursor() as cur:
        cur.execute(
            """
            INSERT INTO payments (charter_id, amount, payment_date,
            payment_method, payment_key, notes, last_updated)
            VALUES (%s, %s, COALESCE(%s, CURRENT_DATE), %s, %s, %s, NOW())
            RETURNING payment_id, charter_id, amount, payment_date,
            payment_method, payment_key, notes, created_at, last_updated
            """,
            (
                charter_id,
                body.amount,
                body.payment_date,
                body.payment_method or "credit_card",
                body.payment_key,
                body.notes,
            ),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=500, detail="insert_failed")
        cols = [d[0] for d in (cur.description or [])]
        item = dict(zip(cols, row, strict=False))
        ensure_audit_storage(cur.connection)
        record_audit_event(
            cur.connection,
            AuditEvent(
                module="payments",
                entity_type="payment",
                entity_id=str(item["payment_id"]),
                action="create_payment",
                source="api",
                actor=_audit_actor(request),
                before=None,
                after=item,
                evidence_links=[],
                retention_until=date.today() + timedelta(days=365 * 7),
                note="Payment created through API",
            ),
            ensure_storage=False,
            commit=False,
        )
    return {"payment": item}


@router.patch("/payments/{payment_id}")
def update_payment(
    payment_id: int,
    body: PaymentUpdate,
    request: Request,
) -> dict[str, Any]:
    updates = {k: v for k, v in body.model_dump(exclude_none=True).items()}
    if not updates:
        raise HTTPException(status_code=400, detail="no_fields")
    sets = ", ".join([f"{k} = %s" for k in updates])
    values = [*list(updates.values()), payment_id]
    with cursor() as cur:
        before_snapshot = _load_payment_snapshot(cur, payment_id)
        if not before_snapshot:
            raise HTTPException(status_code=404, detail="not_found")
        cur.execute(
            f"UPDATE payments SET {sets}, last_updated = NOW() WHERE"
            f"payment_id = %s RETURNING payment_id, charter_id, amount,"
            f"payment_date, payment_method, payment_key, notes, created_at,"
            f"last_updated",
            values,
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="not_found")
        cols = [d[0] for d in (cur.description or [])]
        item = dict(zip(cols, row, strict=False))
        ensure_audit_storage(cur.connection)
        record_audit_event(
            cur.connection,
            AuditEvent(
                module="payments",
                entity_type="payment",
                entity_id=str(payment_id),
                action="update_payment",
                source="api",
                actor=_audit_actor(request),
                before=before_snapshot,
                after=item,
                evidence_links=[],
                retention_until=date.today() + timedelta(days=365 * 7),
                note="Payment updated through API",
            ),
            ensure_storage=False,
            commit=False,
        )
    return {"payment": item}


@router.delete("/payments/{payment_id}")
def delete_payment(payment_id: int, request: Request) -> dict[str, Any]:
    with cursor() as cur:
        before_snapshot = _load_payment_snapshot(cur, payment_id)
        if not before_snapshot:
            raise HTTPException(status_code=404, detail="not_found")
        cur.execute(
            "DELETE FROM payments WHERE payment_id = %s", (payment_id,)
        )
        deleted = cur.rowcount
        if not deleted:
            raise HTTPException(status_code=404, detail="not_found")
        ensure_audit_storage(cur.connection)
        record_audit_event(
            cur.connection,
            AuditEvent(
                module="payments",
                entity_type="payment",
                entity_id=str(payment_id),
                action="delete_payment",
                source="api",
                actor=_audit_actor(request),
                before=before_snapshot,
                after=None,
                evidence_links=[],
                retention_until=date.today() + timedelta(days=365 * 7),
                note="Payment deleted through API",
            ),
            ensure_storage=False,
            commit=False,
        )
    return {"deleted": True}
