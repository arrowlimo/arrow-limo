from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional

from ..db import get_connection

router = APIRouter(prefix="/receipts", tags=["receipts-split"])


class SplitRequest(BaseModel):
    base_amount: Optional[float] = None
    note: Optional[str] = None


def _choose_amount_and_column(row: dict) -> tuple[float, str]:
    for col in ("expense", "gross_amount", "net_amount"):
        val = float(row.get(col) or 0)
        if val and abs(val) > 0.0:
            return val, col
    return 0.0, "expense"


@router.post("/{receipt_id}/auto-split")
def auto_split_receipt(receipt_id: int, req: SplitRequest):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT receipt_id, vendor_name, canonical_vendor, vendor_account_id,
                   receipt_date, description, category,
                   COALESCE(expense, 0) AS expense,
                   COALESCE(gross_amount, 0) AS gross_amount,
                   COALESCE(net_amount, 0) AS net_amount,
                   parent_receipt_id
            FROM receipts WHERE receipt_id=%s
            """,
            (receipt_id,),
        )
        r = cur.fetchone()
        if not r:
            return {"status": "not_found", "receipt_id": receipt_id}

        row = {
            "receipt_id": r[0],
            "vendor_name": r[1],
            "canonical_vendor": r[2],
            "vendor_account_id": r[3],
            "receipt_date": r[4],
            "description": r[5] or "",
            "category": r[6],
            "expense": float(r[7] or 0.0),
            "gross_amount": float(r[8] or 0.0),
            "net_amount": float(r[9] or 0.0),
            "parent_receipt_id": r[10],
        }

        total, amt_col = _choose_amount_and_column(row)
        if total <= 0.0:
            return {"status": "skip", "reason": "no_amount_to_split", "receipt_id": receipt_id}

        # Base amount: override if provided, else try parse from description numbers
        base = req.base_amount
        if base is None:
            import re
            nums = re.findall(r"([0-9]+\.[0-9]{2})", (row["description"] or "").lower())
            if nums:
                # pick the largest number assumption for base
                try:
                    base = float(sorted(nums, key=lambda x: float(x))[-1])
                except Exception:
                    base = None

        if base is None:
            return {"status": "needs_input", "reason": "base_amount_required", "receipt_id": receipt_id}

        fee = round(total - base, 2)
        if fee <= 0.0:
            return {"status": "skip", "reason": "no_positive_fee", "receipt_id": receipt_id, "base": base, "total": total}

        # Idempotency: look for an existing child with signature
        signature = f"AUTO_SPLIT_FEE|parent={receipt_id}|fee={fee:.2f}"
        cur.execute(
            "SELECT receipt_id FROM receipts WHERE description LIKE %s AND (LOWER(vendor_name)=LOWER(%s) OR LOWER(canonical_vendor)=LOWER(%s))",
            (signature + '%', row["vendor_name"], row["vendor_name"]),
        )
        existing = cur.fetchone()
        fee_id = None
        if not existing:
            cur.execute(
                """
                INSERT INTO receipts (
                    vendor_name, canonical_vendor, vendor_account_id,
                    receipt_date, expense, description, parent_receipt_id
                ) VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING receipt_id
                """,
                (
                    row["vendor_name"], row["canonical_vendor"], row["vendor_account_id"],
                    row["receipt_date"], fee,
                    signature + " | OD/Late fee",
                    receipt_id,
                ),
            )
            fee_id = cur.fetchone()[0]

        # Update parent amount column to base
        cur.execute(f"UPDATE receipts SET {amt_col}=%s WHERE receipt_id=%s", (base, receipt_id))
        conn.commit()
        return {"status": "ok", "receipt_id": receipt_id, "base": base, "fee": fee, "fee_receipt_id": fee_id, "amount_column": amt_col}
    except Exception as e:
        conn.rollback()
        return {"status": "error", "error": str(e)}
    finally:
        try:
            conn.close()
        except Exception:
            pass
