from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from ..audit.engine import ensure_audit_storage, record_audit_event
from ..audit.schemas import AuditEvent, AuditEventActor
from ..db import cursor

router = APIRouter(prefix="/api/client-credits", tags=["client-credits"])


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


def _load_credit_snapshot(cur, credit_id: int) -> dict[str, Any] | None:
    cur.execute(
        """
        SELECT credit_id, source_reserve_number, source_charter_id, client_id,
               credit_amount, credit_reason, remaining_balance, created_date,
               applied_date, applied_to_reserve_number, applied_to_charter_id,
               notes, created_by
        FROM charter_credit_ledger
        WHERE credit_id = %s
        """,
        (credit_id,),
    )
    row = cur.fetchone()
    if not row:
        return None
    cols = [d[0] for d in (cur.description or [])]
    payload = dict(zip(cols, row, strict=False))
    payload["credit_amount"] = Decimal(str(payload.get("credit_amount") or 0))
    payload["remaining_balance"] = Decimal(str(payload.get("remaining_balance") or 0))
    return payload


def _load_credit_summary(cur, client_id: int) -> dict[str, Any]:
    cur.execute(
        """
        SELECT
            COUNT(*) AS credit_count,
            COALESCE(SUM(credit_amount), 0) AS total_credit_amount,
            COALESCE(SUM(remaining_balance), 0) AS available_credit_amount
        FROM charter_credit_ledger
        WHERE client_id = %s
        """,
        (client_id,),
    )
    row = cur.fetchone() or (0, 0, 0)
    return {
        "credit_count": int(row[0] or 0),
        "total_credit_amount": Decimal(str(row[1] or 0)),
        "available_credit_amount": Decimal(str(row[2] or 0)),
    }


class ClientCreditCreate(BaseModel):
    client_id: int
    credit_amount: Decimal = Field(..., gt=0)
    credit_reason: str = Field(..., min_length=1)
    source_reserve_number: str | None = None
    source_charter_id: int | None = None
    notes: str | None = None
    created_by: str | None = None


class ClientCreditApply(BaseModel):
    applied_to_charter_id: int
    applied_to_reserve_number: str | None = None
    amount: Decimal | None = None
    notes: str | None = None
    applied_by: str | None = None


@router.get("/{client_id:int}")
def list_client_credits(client_id: int) -> dict[str, Any]:
    with cursor() as cur:
        cur.execute(
            """
            SELECT credit_id, source_reserve_number, source_charter_id, client_id,
                   credit_amount, credit_reason, remaining_balance, created_date,
                   applied_date, applied_to_reserve_number, applied_to_charter_id,
                   notes, created_by
            FROM charter_credit_ledger
            WHERE client_id = %s
            ORDER BY created_date DESC, credit_id DESC
            """,
            (client_id,),
        )
        rows = cur.fetchall()
        cols = [d[0] for d in (cur.description or [])]
        credit_rows = []
        for row in rows:
            item = dict(zip(cols, row, strict=False))
            item["credit_amount"] = float(item.get("credit_amount") or 0)
            item["remaining_balance"] = float(item.get("remaining_balance") or 0)
            credit_rows.append(item)
        summary = _load_credit_summary(cur, client_id)
    return {
        "client_id": client_id,
        "summary": {
            **summary,
            "total_credit_amount": float(summary["total_credit_amount"]),
            "available_credit_amount": float(summary["available_credit_amount"]),
        },
        "credits": credit_rows,
    }


@router.post(
    "/",
    status_code=201,
    responses={500: {"description": "Failed to create the credit ledger entry"}},
)
def create_client_credit(body: ClientCreditCreate, request: Request) -> dict[str, Any]:
    with cursor() as cur:
        cur.execute(
            """
            INSERT INTO charter_credit_ledger (
                source_reserve_number,
                source_charter_id,
                client_id,
                credit_amount,
                credit_reason,
                remaining_balance,
                created_date,
                applied_date,
                applied_to_reserve_number,
                applied_to_charter_id,
                notes,
                created_by
            ) VALUES (%s, %s, %s, %s, %s, %s, CURRENT_DATE, NULL, NULL, NULL, %s, %s)
            RETURNING credit_id
            """,
            (
                body.source_reserve_number,
                body.source_charter_id,
                body.client_id,
                body.credit_amount,
                body.credit_reason.strip(),
                body.credit_amount,
                body.notes,
                body.created_by or (_audit_actor(request).username or "system"),
            ),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=500, detail="credit_insert_failed")
        credit_id = int(row[0])
        snapshot = _load_credit_snapshot(cur, credit_id)
        if snapshot is None:
            raise HTTPException(status_code=500, detail="credit_snapshot_missing")
        ensure_audit_storage(cur.connection)
        record_audit_event(
            cur.connection,
            AuditEvent(
                module="client_credits",
                entity_type="charter_credit_ledger",
                entity_id=str(credit_id),
                action="create_credit",
                source="api",
                actor=_audit_actor(request),
                before=None,
                after=snapshot,
                evidence_links=[],
                retention_until=date.today() + timedelta(days=365 * 7),
                note="Client credit created through API",
            ),
            ensure_storage=False,
            commit=False,
        )
    return {"credit": snapshot}


@router.post(
    "/{credit_id:int}/apply",
    responses={
        400: {"description": "Invalid application amount"},
        404: {"description": "Credit ledger entry not found"},
        409: {"description": "Credit has already been fully applied"},
        500: {"description": "Failed to update the credit ledger entry"},
    },
)
def apply_client_credit(credit_id: int, body: ClientCreditApply, request: Request) -> dict[str, Any]:
    apply_amount = body.amount
    with cursor() as cur:
        before_snapshot = _load_credit_snapshot(cur, credit_id)
        if before_snapshot is None:
            raise HTTPException(status_code=404, detail="credit_not_found")

        remaining_balance = Decimal(str(before_snapshot.get("remaining_balance") or 0))
        if remaining_balance <= 0:
            raise HTTPException(status_code=409, detail="credit_already_fully_applied")

        if apply_amount is None:
            apply_amount = remaining_balance
        else:
            apply_amount = Decimal(str(apply_amount))

        if apply_amount <= 0:
            raise HTTPException(status_code=400, detail="apply_amount_must_be_positive")
        if abs(apply_amount - remaining_balance) > Decimal("0.01"):
            raise HTTPException(
                status_code=400,
                detail=(
                    "partial_application_not_supported; "
                    "apply the full remaining balance or split the credit into separate ledger entries"
                ),
            )

        cur.execute(
            """
            UPDATE charter_credit_ledger
            SET remaining_balance = 0,
                applied_date = CURRENT_DATE,
                applied_to_reserve_number = %s,
                applied_to_charter_id = %s,
                notes = COALESCE(notes, '')
                    || CASE WHEN COALESCE(notes, '') = '' THEN '' ELSE E'\n' END
                    || COALESCE(%s, ''),
                created_by = COALESCE(created_by, %s)
            WHERE credit_id = %s
            RETURNING credit_id
            """,
            (
                body.applied_to_reserve_number,
                body.applied_to_charter_id,
                body.notes,
                body.applied_by or (_audit_actor(request).username or "system"),
                credit_id,
            ),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="credit_not_found")

        after_snapshot = _load_credit_snapshot(cur, credit_id)
        if after_snapshot is None:
            raise HTTPException(status_code=500, detail="credit_snapshot_missing")

        ensure_audit_storage(cur.connection)
        record_audit_event(
            cur.connection,
            AuditEvent(
                module="client_credits",
                entity_type="charter_credit_ledger",
                entity_id=str(credit_id),
                action="apply_credit",
                source="api",
                actor=_audit_actor(request),
                before=before_snapshot,
                after=after_snapshot,
                evidence_links=[],
                retention_until=date.today() + timedelta(days=365 * 7),
                note="Client credit applied through API",
            ),
            ensure_storage=False,
            commit=False,
        )
    return {"credit": after_snapshot}
