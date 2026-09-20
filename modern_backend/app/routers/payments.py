from datetime import date, timedelta
import re
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from ..audit.engine import ensure_audit_storage, record_audit_event
from ..audit.schemas import AuditEvent, AuditEventActor
from ..db import cursor

router = APIRouter(prefix="/api", tags=["payments"])


def _normalize_payment_method(value: str | None) -> str:
    raw = (value or "").strip().lower()
    if not raw:
        return "credit_card"

    alias_map = {
        "etransfer": "e_transfer",
        "e-transfer": "e_transfer",
        "email transfer": "e_transfer",
        "cheque": "check",
        "cc": "credit_card",
        "credit card": "credit_card",
        "debit card": "debit_card",
        "bank transfer": "bank_transfer",
        "trade": "trade_of_services",
        "trade of services": "trade_of_services",
        "credit": "credit_adjustment",
        "nrr": "e_transfer",
        "retainer": "e_transfer",
    }
    normalized = alias_map.get(raw, raw)

    allowed = {
        "cash",
        "check",
        "credit_card",
        "debit_card",
        "bank_transfer",
        "e_transfer",
        "trade_of_services",
        "unknown",
        "credit_adjustment",
    }
    return normalized if normalized in allowed else "unknown"


def _audit_actor(request: Request | None) -> AuditEventActor:
    if request is None:
        return AuditEventActor(actor_type="system", username="system")
    username = request.headers.get("X-User-Name") or request.headers.get("X-User")
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
    nrr_portion: float | None = None


class PaymentUpdate(BaseModel):
    amount: float | None = None
    payment_date: str | None = None
    payment_method: str | None = None
    payment_key: str | None = None
    notes: str | None = None


def _insert_payment_row(
    cur,
    *,
    charter_id: int,
    amount: float,
    payment_date: str | None,
    payment_method: str | None,
    payment_key: str | None,
    notes: str | None,
) -> dict[str, Any]:
    normalized_method = _normalize_payment_method(payment_method)
    cur.execute(
        """
        INSERT INTO payments (charter_id, reserve_number, amount, payment_date,
        payment_method, payment_key, notes, last_updated)
        SELECT c.charter_id, c.reserve_number, %s, COALESCE(%s, CURRENT_DATE),
               %s, %s, %s, NOW()
        FROM charters c
        WHERE c.charter_id = %s
        RETURNING payment_id, charter_id, reserve_number, amount, payment_date,
        payment_method, payment_key, notes, created_at, last_updated
        """,
        (
            amount,
            payment_date,
            normalized_method,
            payment_key,
            notes,
            charter_id,
        ),
    )
    row = cur.fetchone()
    if not row:
        raise RuntimeError("insert_failed")
    cols = [d[0] for d in (cur.description or [])]
    return dict(zip(cols, row, strict=False))


def _extract_nrr_portion_from_text(value: str | None) -> float:
    text = (value or "").strip()
    if not text:
        return 0.0

    bracket_match = re.search(r"\[NRR_PART:\s*(\d+(?:\.\d{1,2})?)\]", text, flags=re.IGNORECASE)
    if bracket_match:
        try:
            return float(bracket_match.group(1))
        except Exception:
            return 0.0

    normalized = text.replace(",", "")
    plain_match = re.search(r"\bnrr\b\D{0,12}(\d+(?:\.\d{1,2})?)", normalized, flags=re.IGNORECASE)
    if plain_match:
        try:
            return float(plain_match.group(1).replace("$", ""))
        except Exception:
            return 0.0
    return 0.0


def _strip_nrr_marker_text(value: str | None) -> str | None:
    text = (value or "").strip()
    if not text:
        return None
    text = re.sub(r"\[NRR_PART:\s*\d+(?:\.\d{1,2})?\]", "", text, flags=re.IGNORECASE).strip()
    text = re.sub(r"\bnrr\b\D{0,12}\d+(?:\.\d{1,2})?", "", text, flags=re.IGNORECASE).strip()
    text = re.sub(r"\s{2,}", " ", text).strip()
    return text or None


def _resolved_nrr_portion(body: PaymentCreate) -> float:
    if body.nrr_portion is not None:
        try:
            return max(0.0, float(body.nrr_portion))
        except Exception:
            return 0.0

    from_key = _extract_nrr_portion_from_text(body.payment_key)
    if from_key > 0:
        return from_key
    return _extract_nrr_portion_from_text(body.notes)


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
        total_amount = max(0.0, float(body.amount or 0))
        nrr_portion = min(_resolved_nrr_portion(body), total_amount)
        base_amount = round(total_amount - nrr_portion, 2)

        cleaned_payment_key = _strip_nrr_marker_text(body.payment_key)
        cleaned_notes = _strip_nrr_marker_text(body.notes)

        if nrr_portion > 0 and base_amount > 0:
            item = _insert_payment_row(
                cur,
                charter_id=charter_id,
                amount=base_amount,
                payment_date=body.payment_date,
                payment_method=body.payment_method,
                payment_key=cleaned_payment_key,
                notes=cleaned_notes,
            )
            nrr_item = _insert_payment_row(
                cur,
                charter_id=charter_id,
                amount=round(nrr_portion, 2),
                payment_date=body.payment_date,
                payment_method=body.payment_method,
                payment_key="[TYPE:NRR Retainer]",
                notes=(cleaned_notes or "") or None,
            )

            ensure_audit_storage(cur.connection)
            for created in (item, nrr_item):
                record_audit_event(
                    cur.connection,
                    AuditEvent(
                        module="payments",
                        entity_type="payment",
                        entity_id=str(created["payment_id"]),
                        action="create_payment",
                        source="api",
                        actor=_audit_actor(request),
                        before=None,
                        after=created,
                        evidence_links=[],
                        retention_until=date.today() + timedelta(days=365 * 7),
                        note="Split payment created through API",
                    ),
                    ensure_storage=False,
                    commit=False,
                )
            return {
                "payment": item,
                "split": True,
                "split_payments": [item, nrr_item],
                "nrr_payment": nrr_item,
            }

        if nrr_portion > 0 and base_amount <= 0:
            item = _insert_payment_row(
                cur,
                charter_id=charter_id,
                amount=round(nrr_portion, 2),
                payment_date=body.payment_date,
                payment_method=body.payment_method,
                payment_key="[TYPE:NRR Retainer]",
                notes=cleaned_notes,
            )
        else:
            item = _insert_payment_row(
                cur,
                charter_id=charter_id,
                amount=total_amount,
                payment_date=body.payment_date,
                payment_method=body.payment_method,
                payment_key=cleaned_payment_key,
                notes=cleaned_notes,
            )

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
    updates = dict(body.model_dump(exclude_none=True).items())
    if not updates:
        raise HTTPException(status_code=400, detail="no_fields")
    sets = ", ".join([f"{k} = %s" for k in updates])
    values = [*list(updates.values()), payment_id]
    with cursor() as cur:
        before_snapshot = _load_payment_snapshot(cur, payment_id)
        if not before_snapshot:
            raise HTTPException(status_code=404, detail="not_found")
        cur.execute(
            f"UPDATE payments SET {sets}, last_updated = NOW() WHERE "
            f"payment_id = %s RETURNING payment_id, charter_id, amount, "
            f"payment_date, payment_method, payment_key, notes, created_at, "
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

        # Legacy used payments can be referenced by ledger/reconciliation rows.
        # Detach those links so delete can proceed safely.
        cur.execute(
            """
            UPDATE income_ledger
            SET payment_id = NULL
            WHERE payment_id = %s
            """,
            (payment_id,),
        )
        detached_income_rows = cur.rowcount or 0

        cur.execute(
            """
            UPDATE square_etransfer_reconciliation
            SET square_payment_id = NULL
            WHERE square_payment_id = %s
            """,
            (payment_id,),
        )
        detached_reconciliation_rows = cur.rowcount or 0

        cur.execute("DELETE FROM payments WHERE payment_id = %s", (payment_id,))
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
                note=(
                    "Payment deleted through API "
                    f"(detached income_ledger={int(detached_income_rows)}, "
                    f"reconciliation={int(detached_reconciliation_rows)})"
                ),
            ),
            ensure_storage=False,
            commit=False,
        )
    return {
        "deleted": True,
        "detached_income_ledger_rows": int(detached_income_rows),
        "detached_reconciliation_rows": int(detached_reconciliation_rows),
    }
