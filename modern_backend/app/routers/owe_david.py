"""Owe David dashboard – reads from david_account_tracking table."""

from fastapi import APIRouter, HTTPException

from ..db import get_connection

router = APIRouter(prefix="/api/owe-david", tags=["owe-david"])


@router.get("/transactions")
def list_owe_david_transactions():
    """Return all David account transactions ordered newest first."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT
                id,
                transaction_date,
                description,
                debit_amount,
                credit_amount,
                running_balance,
                source_reference,
                notes
            FROM david_account_tracking
            ORDER BY transaction_date DESC, id DESC
            """
        )
        rows = cur.fetchall()
        result = []
        for row in rows:
            (
                tid,
                tdate,
                description,
                debit,
                credit,
                balance,
                source_ref,
                notes,
            ) = row
            debit = float(debit or 0)
            credit = float(credit or 0)
            if debit > 0:
                ttype = "expense"
                amount = debit
            else:
                ttype = "payment"
                amount = credit
            result.append(
                {
                    "id": tid,
                    "date": str(tdate) if tdate else None,
                    "type": ttype,
                    "amount": amount,
                    "description": description or "",
                    "reference": source_ref or "",
                    "category": "",
                    "status": "complete",
                    "running_balance": float(balance or 0),
                    "notes": notes or "",
                }
            )
        return result
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to load David account transactions: {e}",
        ) from e
    finally:
        cur.close()
        conn.close()
