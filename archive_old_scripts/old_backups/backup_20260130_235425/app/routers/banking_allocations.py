from fastapi import APIRouter
from pydantic import BaseModel, Field
from typing import List

from ..db import get_connection

router = APIRouter(prefix="/banking", tags=["banking-allocations"])


class Allocation(BaseModel):
    receipt_id: int
    amount: float = Field(gt=0)


class AllocationRequest(BaseModel):
    allocations: List[Allocation]
    created_by: str = "desktop-app"


@router.get("/{transaction_id}/allocations/preview")
def preview_allocations(transaction_id: int):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT transaction_id, transaction_date, debit_amount, description FROM banking_transactions WHERE transaction_id=%s",
            (transaction_id,),
        )
        bt = cur.fetchone()
        if not bt:
            return {"status": "not_found", "transaction_id": transaction_id}

        cur.execute(
            "SELECT r.receipt_id, r.vendor_name, r.gross_amount, r.description FROM receipts r WHERE r.banking_transaction_id=%s",
            (transaction_id,),
        )
        linked = cur.fetchall()
        return {
            "status": "ok",
            "transaction": {
                "transaction_id": bt[0],
                "date": bt[1],
                "debit_amount": float(bt[2] or 0.0),
                "description": bt[3],
            },
            "linked_receipts": [
                {
                    "receipt_id": r[0],
                    "vendor": r[1],
                    "amount": float(r[2] or 0.0),
                    "description": r[3],
                }
                for r in linked
            ],
        }
    finally:
        try:
            conn.close()
        except Exception:
            pass


@router.post("/{transaction_id}/allocate")
def allocate_banking_to_receipts(transaction_id: int, req: AllocationRequest):
    conn = get_connection()
    try:
        cur = conn.cursor()

        cur.execute(
            "SELECT transaction_id, transaction_date, debit_amount, description FROM banking_transactions WHERE transaction_id=%s",
            (transaction_id,),
        )
        bt = cur.fetchone()
        if not bt:
            return {"status": "not_found", "transaction_id": transaction_id}

        debit_amount = float(bt[2] or 0.0)
        total_alloc = round(sum(a.amount for a in req.allocations), 2)
        if total_alloc <= 0:
            return {"status": "error", "error": "total_allocation_must_be_positive"}

        # Allow small tolerance in matching; do not exceed debit by more than $0.50
        if total_alloc - debit_amount > 0.50:
            return {"status": "error", "error": "allocations_exceed_debit", "debit_amount": debit_amount, "total_allocations": total_alloc}

        # Apply idempotently
        for a in req.allocations:
            # Link receipt to banking transaction
            cur.execute("UPDATE receipts SET banking_transaction_id=%s WHERE receipt_id=%s", (transaction_id, a.receipt_id))

            # Insert ledger row if not present
            cur.execute(
                "SELECT id FROM banking_receipt_matching_ledger WHERE banking_transaction_id=%s AND receipt_id=%s",
                (transaction_id, a.receipt_id),
            )
            existing = cur.fetchone()
            if not existing:
                cur.execute(
                    """
                    INSERT INTO banking_receipt_matching_ledger (
                        banking_transaction_id, receipt_id, match_date, match_type, match_status, match_confidence, notes, created_by
                    ) VALUES (
                        %s, %s, NOW(), %s, %s, %s, %s, %s
                    )
                    """,
                    (
                        transaction_id,
                        a.receipt_id,
                        "allocation",
                        "linked",
                        "exact" if abs(a.amount - debit_amount) < 0.01 else "partial",
                        f"amount={a.amount:.2f}",
                        req.created_by,
                    ),
                )
            else:
                # Update notes to reflect latest amount
                cur.execute(
                    "UPDATE banking_receipt_matching_ledger SET notes=%s WHERE id=%s",
                    (f"amount={a.amount:.2f}", existing[0]),
                )

        conn.commit()
        return {"status": "ok", "transaction_id": transaction_id, "total_allocations": total_alloc, "debit_amount": debit_amount}
    except Exception as e:
        conn.rollback()
        return {"status": "error", "error": str(e)}
    finally:
        try:
            conn.close()
        except Exception:
            pass
