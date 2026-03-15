"""Bank Account Reconciliation Report for Auditors

Provides bank account-specific reconciliation with opening/closing balances, 
running balance calculations, and per-account summary statistics.

Endpoints:
  GET /api/bank-audit/account-reconciliation - Main audit report by bank account
  GET /api/bank-audit/accounts - List all bank accounts
"""

import logging

from fastapi import APIRouter, Query

from ..db import get_connection

router = APIRouter(prefix="/api/bank-audit", tags=["bank-audit"])
logger = logging.getLogger(__name__)


class BankTransactionLine:
    """Single transaction with running balance"""
    def __init__(self, row):
        self.transaction_date = row[0]
        self.description = row[1]
        self.amount = float(row[2]) if row[2] else 0
        self.banking_transaction_id = row[3]
        self.receipt_vendor = row[4]
        self.receipt_id = row[5]
        self.receipt_total = float(row[6]) if row[6] else None
        self.linked = row[7] is not None
        self.running_balance = 0.0  # Set by caller


class BankAccountSummary:
    """Per-account reconciliation summary"""
    def __init__(self, account_number):
        self.account_number = account_number
        self.account_name = None
        self.opening_balance = 0.0
        self.closing_balance = 0.0
        self.total_debits = 0.0
        self.total_credits = 0.0
        self.transaction_count = 0
        self.linked_count = 0
        self.unlinked_count = 0
        self.total_unlinked_amount = 0.0
        self.transactions: list[BankTransactionLine] = []
        self.variance = 0.0


@router.get("/accounts")
async def list_bank_accounts():
    """List all unique bank accounts in the system"""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT DISTINCT account_number, account_name, institution_name
            FROM banking_transactions
            WHERE account_number IS NOT NULL
            ORDER BY institution_name, account_number
        """)
        
        accounts = []
        for row in cur.fetchall():
            accounts.append({
                "account_number": row[0],
                "account_name": row[1],
                "institution_name": row[2]
            })
        
        cur.close()
        return {"accounts": accounts}
    except Exception as e:
        logger.error(f"Error fetching bank accounts: {e}")
        return {"error": str(e), "accounts": []}


@router.get("/account-reconciliation")
async def get_account_reconciliation(
    start_date: str = Query(..., description="Start date (YYYY-MM-DD)"),
    end_date: str = Query(..., description="End date (YYYY-MM-DD)"),
    account_number: str | None = Query(None, description="Filter by account number"),
):
    """
    Get bank account reconciliation report with opening/closing balances and running balance.
    
    Returns transactions grouped by bank account with:
    - Opening balance (balance before period start)
    - Closing balance (balance after period end)
    - Running balance for each transaction
    - Receipt linking status
    - Account-level summary statistics
    """
    conn = get_connection()
    try:
        cur = conn.cursor()
        
        # Build account list
        if account_number:
            account_filter = "AND bt.account_number = %s"
            account_params = [account_number]
        else:
            account_filter = ""
            account_params = []
        
        # Get distinct accounts
        cur.execute(f"""
            SELECT DISTINCT account_number, account_name, institution_name
            FROM banking_transactions
            WHERE 1=1 {account_filter}
            ORDER BY institution_name, account_number
        """, account_params)
        
        accounts = cur.fetchall()
        results = []
        
        for acc in accounts:
            acc_number = acc[0]
            acc_name = acc[1]
            institution = acc[2]
            
            summary = BankAccountSummary(acc_number)
            summary.account_name = acc_name
            
            # Get opening balance (sum of all transactions BEFORE period)
            cur.execute("""
                SELECT COALESCE(SUM(amount), 0)
                FROM banking_transactions
                WHERE account_number = %s AND transaction_date < %s
            """, [acc_number, start_date])
            
            opening_bal = cur.fetchone()[0]
            summary.opening_balance = float(opening_bal) if opening_bal else 0.0
            
            # Get transactions in period with receipt info
            cur.execute("""
                SELECT 
                    bt.transaction_date,
                    bt.description,
                    bt.amount,
                    bt.transaction_id,
                    r.vendor_name,
                    r.receipt_id,
                    r.total_amount,
                    r.receipt_id  -- Used to determine if linked (not null = linked)
                FROM banking_transactions bt
                LEFT JOIN receipts r ON bt.transaction_id = r.banking_transaction_id
                WHERE bt.account_number = %s
                    AND bt.transaction_date BETWEEN %s AND %s
                ORDER BY bt.transaction_date, bt.transaction_id
            """, [acc_number, start_date, end_date])
            
            transaction_rows = cur.fetchall()
            running_balance = summary.opening_balance
            
            for row in transaction_rows:
                trans = BankTransactionLine(row)
                trans.running_balance = running_balance + trans.amount
                running_balance = trans.running_balance
                
                summary.transactions.append(trans)
                summary.transaction_count += 1
                summary.total_debits += trans.amount if trans.amount < 0 else 0
                summary.total_credits += trans.amount if trans.amount > 0 else 0
                
                if trans.linked:
                    summary.linked_count += 1
                else:
                    summary.unlinked_count += 1
                    summary.total_unlinked_amount += trans.amount
            
            # Set closing balance
            summary.closing_balance = running_balance
            
            # Get actual balance from bank statement (if stored)
            cur.execute("""
                SELECT balance_at_date
                FROM bank_statement_balances
                WHERE account_number = %s AND statement_date = %s
            """, [acc_number, end_date])
            
            stmt_bal = cur.fetchone()
            if stmt_bal:
                actual_closing = float(stmt_bal[0])
                summary.variance = actual_closing - summary.closing_balance
            
            results.append({
                "account_number": acc_number,
                "account_name": acc_name,
                "institution_name": institution,
                "opening_balance": summary.opening_balance,
                "closing_balance": summary.closing_balance,
                "variance": summary.variance,
                "total_credits": summary.total_credits,
                "total_debits": summary.total_debits,
                "transaction_count": summary.transaction_count,
                "linked_count": summary.linked_count,
                "unlinked_count": summary.unlinked_count,
                "total_unlinked_amount": summary.total_unlinked_amount,
                "transactions": [
                    {
                        "transaction_date": str(t.transaction_date),
                        "description": t.description,
                        "amount": t.amount,
                        "running_balance": t.running_balance,
                        "banking_transaction_id": t.banking_transaction_id,
                        "receipt_vendor": t.receipt_vendor,
                        "receipt_id": t.receipt_id,
                        "receipt_total": t.receipt_total,
                        "linked": t.linked
                    }
                    for t in summary.transactions
                ]
            })
        
        cur.close()
        
        return {
            "report_period": {
                "start_date": start_date,
                "end_date": end_date
            },
            "accounts": results,
            "account_count": len(results),
            "total_linked": sum(acc["linked_count"] for acc in results),
            "total_unlinked": sum(acc["unlinked_count"] for acc in results),
            "total_variance": sum(acc["variance"] for acc in results)
        }
        
    except Exception as e:
        logger.error(f"Error generating account reconciliation report: {e}")
        return {
            "error": str(e),
            "report_period": {"start_date": start_date, "end_date": end_date},
            "accounts": []
        }
    finally:
        cur.close()


@router.get("/account-summary")
async def get_account_summary(
    account_number: str = Query(..., description="Bank account number"),
    start_date: str = Query(..., description="Start date (YYYY-MM-DD)"),
    end_date: str = Query(..., description="End date (YYYY-MM-DD)")
):
    """
    Get summary statistics for a specific bank account in the period.
    Useful for dashboard display and quick audit checks.
    """
    conn = get_connection()
    try:
        cur = conn.cursor()
        
        # Get account details
        cur.execute("""
            SELECT account_name, institution_name, account_type
            FROM banking_transactions
            WHERE account_number = %s
            LIMIT 1
        """, [account_number])
        
        acc_info = cur.fetchone()
        if not acc_info:
            return {"error": "Account not found", "account_number": account_number}
        
        # Opening balance
        cur.execute("""
            SELECT COALESCE(SUM(amount), 0)
            FROM banking_transactions
            WHERE account_number = %s AND transaction_date < %s
        """, [account_number, start_date])
        opening_bal = float(cur.fetchone()[0]) or 0
        
        # Period transactions
        cur.execute("""
            SELECT 
                COALESCE(SUM(CASE WHEN amount > 0 THEN amount ELSE 0 END), 0) as credits,
                COALESCE(SUM(CASE WHEN amount < 0 THEN ABS(amount) ELSE 0 END), 0) as debits,
                COUNT(*) as transaction_count,
                COUNT(CASE WHEN r.receipt_id IS NOT NULL THEN 1 END) as linked_count,
                COALESCE(SUM(CASE WHEN r.receipt_id IS NULL THEN ABS(amount) ELSE 0 END), 0) as unlinked_amount
            FROM banking_transactions bt
            LEFT JOIN receipts r ON bt.transaction_id = r.banking_transaction_id
            WHERE bt.account_number = %s
                AND bt.transaction_date BETWEEN %s AND %s
        """, [account_number, start_date, end_date])
        
        summary_row = cur.fetchone()
        credits = float(summary_row[0]) if summary_row[0] else 0
        debits = float(summary_row[1]) if summary_row[1] else 0
        trans_count = summary_row[2] or 0
        linked = summary_row[3] or 0
        unlinked_amount = float(summary_row[4]) if summary_row[4] else 0
        
        closing_bal = opening_bal + credits - debits
        
        cur.close()
        
        return {
            "account_number": account_number,
            "account_name": acc_info[0],
            "institution_name": acc_info[1],
            "account_type": acc_info[2],
            "period": {"start_date": start_date, "end_date": end_date},
            "opening_balance": opening_bal,
            "total_credits": credits,
            "total_debits": debits,
            "closing_balance": closing_bal,
            "transactions": {
                "total": trans_count,
                "linked": linked,
                "unlinked": trans_count - linked,
                "unlinked_amount": unlinked_amount
            }
        }
        
    except Exception as e:
        logger.error(f"Error generating account summary: {e}")
        return {"error": str(e)}
    finally:
        cur.close()
