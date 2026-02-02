"""Banking Transactions API Router"""
from datetime import date
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from ..db import get_connection

router = APIRouter(prefix="/api/banking", tags=["banking"])


class BankingTransactionResponse(BaseModel):
    transaction_id: int
    account_number: str
    transaction_date: date
    description: str
    debit_amount: Optional[Decimal]
    credit_amount: Optional[Decimal]
    balance: Optional[Decimal]
    category: Optional[str]
    verified: bool


@router.get("/transactions")
def get_banking_transactions(
    account_number: Optional[str] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    category: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
):
    """Get banking transactions with filters"""
    conn = get_connection()
    cur = conn.cursor()

    query = """
        SELECT
            transaction_id,
            account_number,
            transaction_date,
            description,
            debit_amount,
            credit_amount,
            balance,
            category,
            COALESCE(verified, false) as verified
        FROM banking_transactions
        WHERE 1=1
    """
    params = []

    if account_number:
        query += " AND account_number = %s"
        params.append(account_number)
    if start_date:
        query += " AND transaction_date >= %s"
        params.append(start_date)
    if end_date:
        query += " AND transaction_date <= %s"
        params.append(end_date)
    if category:
        query += " AND category = %s"
        params.append(category)

    query += " ORDER BY transaction_date DESC, transaction_id DESC LIMIT %s OFFSET %s"
    params.extend([limit, offset])

    cur.execute(query, params)

    transactions = []
    for row in cur.fetchall():
        transactions.append(
            {
                "transaction_id": row[0],
                "account_number": row[1],
                "transaction_date": row[2],
                "description": row[3],
                "debit_amount": float(row[4]) if row[4] else None,
                "credit_amount": float(row[5]) if row[5] else None,
                "balance": float(row[6]) if row[6] else None,
                "category": row[7],
                "verified": row[8],
            }
        )

    cur.close()
    conn.close()

    return transactions


@router.get("/accounts")
def get_bank_accounts():
    """Get list of bank accounts"""
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT DISTINCT
            account_number,
            COUNT(*) as transaction_count,
            MAX(transaction_date) as latest_transaction
        FROM banking_transactions
        WHERE account_number IS NOT NULL
        GROUP BY account_number
        ORDER BY account_number
    """
    )

    accounts = []
    for row in cur.fetchall():
        accounts.append(
            {
                "account_number": row[0],
                "transaction_count": row[1],
                "latest_transaction": row[2],
            }
        )

    cur.close()
    conn.close()

    return accounts


@router.put("/transactions/{transaction_id}/categorize")
def categorize_transaction(transaction_id: int, category: str):
    """Categorize a banking transaction"""
    conn = get_connection()
    cur = conn.cursor()

    try:
        cur.execute(
            """
            UPDATE banking_transactions
            SET category = %s
            WHERE transaction_id = %s
        """,
            (category, transaction_id),
        )

        if cur.rowcount == 0:
            conn.rollback()
            cur.close()
            conn.close()
            raise HTTPException(status_code=404, detail="Transaction not found")

        conn.commit()
        cur.close()
        conn.close()

        return {"message": "Transaction categorized successfully"}

    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        cur.close()
        conn.close()
        raise HTTPException(status_code=500, detail=f"Failed to categorize: {str(e)}")


@router.get("/reconciliation/status")
def get_reconciliation_status():
    """Get banking reconciliation status"""
    conn = get_connection()
    cur = conn.cursor()

    # Get unmatched credits (deposits not linked to payments)
    cur.execute(
        """
        SELECT COUNT(*), COALESCE(SUM(credit_amount), 0)
        FROM banking_transactions b
        LEFT JOIN payments p ON p.banking_transaction_id = b.transaction_id
        WHERE b.credit_amount > 0
        AND p.payment_id IS NULL
    """
    )
    unmatched_deposits = cur.fetchone()

    # Get unmatched debits (expenses not linked to receipts)
    cur.execute(
        """
        SELECT COUNT(*), COALESCE(SUM(debit_amount), 0)
        FROM banking_transactions b
        LEFT JOIN receipts r ON r.banking_transaction_id = b.transaction_id
        WHERE b.debit_amount > 0
        AND r.receipt_id IS NULL
    """
    )
    unmatched_expenses = cur.fetchone()

    # Get match rates
    cur.execute(
        """
        SELECT
            COUNT(*) FILTER (WHERE p.payment_id IS NOT NULL) as matched,
            COUNT(*) as total
        FROM banking_transactions b
        LEFT JOIN payments p ON p.banking_transaction_id = b.transaction_id
        WHERE b.credit_amount > 0
    """
    )
    deposit_match = cur.fetchone()

    cur.execute(
        """
        SELECT
            COUNT(*) FILTER (WHERE r.receipt_id IS NOT NULL) as matched,
            COUNT(*) as total
        FROM banking_transactions b
        LEFT JOIN receipts r ON r.banking_transaction_id = b.transaction_id
        WHERE b.debit_amount > 0
    """
    )
    expense_match = cur.fetchone()

    cur.close()
    conn.close()

    return {
        "deposits": {
            "unmatched_count": unmatched_deposits[0],
            "unmatched_amount": float(unmatched_deposits[1])
            if unmatched_deposits[1]
            else 0.0,
            "match_rate": (deposit_match[0] / deposit_match[1] * 100)
            if deposit_match[1] > 0
            else 0.0,
        },
        "expenses": {
            "unmatched_count": unmatched_expenses[0],
            "unmatched_amount": float(unmatched_expenses[1])
            if unmatched_expenses[1]
            else 0.0,
            "match_rate": (expense_match[0] / expense_match[1] * 100)
            if expense_match[1] > 0
            else 0.0,
        },
    }
