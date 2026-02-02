from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..db import cursor

router = APIRouter(prefix="/api", tags=["payments"])


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
            SELECT payment_id, charter_id, amount, payment_date, payment_method, payment_key, notes, created_at, last_updated
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
def create_payment(charter_id: int, body: PaymentCreate) -> dict[str, Any]:
    with cursor() as cur:
        cur.execute(
            """
            INSERT INTO payments (charter_id, amount, payment_date, payment_method, payment_key, notes, last_updated)
            VALUES (%s, %s, COALESCE(%s, CURRENT_DATE), %s, %s, %s, NOW())
            RETURNING payment_id, charter_id, amount, payment_date, payment_method, payment_key, notes, created_at, last_updated
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
    return {"payment": item}


@router.patch("/payments/{payment_id}")
def update_payment(payment_id: int, body: PaymentUpdate) -> dict[str, Any]:
    updates = {k: v for k, v in body.model_dump(exclude_none=True).items()}
    if not updates:
        raise HTTPException(status_code=400, detail="no_fields")
    sets = ", ".join([f"{k} = %s" for k in updates])
    values = [*list(updates.values()), payment_id]
    with cursor() as cur:
        cur.execute(
            f"UPDATE payments SET {sets}, last_updated = NOW() WHERE payment_id = %s RETURNING payment_id, charter_id, amount, payment_date, payment_method, payment_key, notes, created_at, last_updated",
            values,
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="not_found")
        cols = [d[0] for d in (cur.description or [])]
        item = dict(zip(cols, row, strict=False))
    return {"payment": item}


@router.delete("/payments/{payment_id}")
def delete_payment(payment_id: int) -> dict[str, Any]:
    with cursor() as cur:
        cur.execute("DELETE FROM payments WHERE payment_id = %s", (payment_id,))
        deleted = cur.rowcount
        if not deleted:
            raise HTTPException(status_code=404, detail="not_found")
    return {"deleted": True}
