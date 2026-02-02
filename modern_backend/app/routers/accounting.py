"""Accounting Dashboard and Financial Stats API Router"""
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..db import get_connection

router = APIRouter(prefix="/api/accounting", tags=["accounting"])


class AccountingStats(BaseModel):
    monthly_revenue: Decimal
    monthly_expenses: Decimal
    monthly_profit: Decimal
    outstanding_receivables: Decimal
    gst_owed: Decimal


class GSTSummary(BaseModel):
    collected: Decimal
    paid: Decimal
    net_owed: Decimal
    period_start: date
    period_end: date


@router.get("/stats")
def get_accounting_stats(month: Optional[int] = None, year: Optional[int] = None):
    """Get accounting dashboard statistics"""
    conn = get_connection()
    cur = conn.cursor()

    # Default to current month/year
    if month is None:
        month = datetime.now().month
    if year is None:
        year = datetime.now().year

    # Monthly Revenue (from charters)
    cur.execute(
        """
        SELECT COALESCE(SUM(total_amount_due), 0)
        FROM charters
        WHERE EXTRACT(MONTH FROM charter_date) = %s
        AND EXTRACT(YEAR FROM charter_date) = %s
    """,
        (month, year),
    )
    monthly_revenue = cur.fetchone()[0] or 0

    # Monthly Expenses (from receipts)
    cur.execute(
        """
        SELECT COALESCE(SUM(gross_amount + COALESCE(gst_amount, 0)), 0)
        FROM receipts
        WHERE EXTRACT(MONTH FROM receipt_date) = %s
        AND EXTRACT(YEAR FROM receipt_date) = %s
        AND category != 'personal'
    """,
        (month, year),
    )
    monthly_expenses = cur.fetchone()[0] or 0

    # Monthly Profit
    monthly_profit = monthly_revenue - monthly_expenses

    # Outstanding Receivables (unpaid charters = outstanding balance)
    cur.execute(
        """
        SELECT COALESCE(SUM(balance), 0)
        FROM charters
        WHERE balance > 0 AND payment_status != 'paid'
    """
    )
    outstanding_receivables = cur.fetchone()[0] or 0

    # GST Owed (collected on revenue - paid on expenses)
    # Simplified: assume GST rate of 5% on revenue and 5% on expenses
    try:
        monthly_revenue_f = float(monthly_revenue) if monthly_revenue else 0
        monthly_expenses_f = float(monthly_expenses) if monthly_expenses else 0
        gst_collected = monthly_revenue_f * 0.05
        gst_paid = (monthly_expenses_f * 0.95) * 0.05 if monthly_expenses_f > 0 else 0
        gst_owed = gst_collected - gst_paid
    except Exception:
        gst_owed = 0

    cur.close()
    conn.close()

    return {
        "monthly_revenue": float(monthly_revenue) if monthly_revenue else 0,
        "monthly_expenses": float(monthly_expenses) if monthly_expenses else 0,
        "monthly_profit": float(monthly_profit) if monthly_profit else 0,
        "outstanding_receivables": float(outstanding_receivables)
        if outstanding_receivables
        else 0,
        "gst_owed": float(gst_owed),
        "month": month,
        "year": year,
    }


@router.get("/gst/summary")
def get_gst_summary(
    period: str = "current",  # current, last, annual
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
):
    """Get GST summary for specified period"""
    conn = get_connection()
    cur = conn.cursor()

    # Determine date range
    if start_date is None or end_date is None:
        today = date.today()

        if period == "current":
            # Current quarter
            quarter = (today.month - 1) // 3 + 1
            start_date = date(today.year, (quarter - 1) * 3 + 1, 1)
            if quarter == 4:
                end_date = date(today.year, 12, 31)
            else:
                end_date = date(today.year, quarter * 3 + 1, 1)

        elif period == "last":
            # Last quarter
            quarter = (today.month - 1) // 3 + 1
            if quarter == 1:
                start_date = date(today.year - 1, 10, 1)
                end_date = date(today.year - 1, 12, 31)
            else:
                start_date = date(today.year, (quarter - 2) * 3 + 1, 1)
                end_date = date(today.year, (quarter - 1) * 3 + 1, 1)

        elif period == "annual":
            # Current year
            start_date = date(today.year, 1, 1)
            end_date = date(today.year, 12, 31)

    # GST Collected (from invoices)
    cur.execute(
        """
        SELECT COALESCE(SUM(gst), 0)
        FROM invoices
        WHERE invoice_date >= %s AND invoice_date <= %s
    """,
        (start_date, end_date),
    )
    gst_collected = cur.fetchone()[0] or 0

    # GST Paid (from receipts)
    cur.execute(
        """
        SELECT COALESCE(SUM(gst_amount), 0)
        FROM receipts
        WHERE receipt_date >= %s AND receipt_date <= %s
        AND category != 'personal'
    """,
        (start_date, end_date),
    )
    gst_paid = cur.fetchone()[0] or 0

    cur.close()
    conn.close()

    return {
        "collected": float(gst_collected),
        "paid": float(gst_paid),
        "net_owed": float(gst_collected - gst_paid),
        "period_start": start_date,
        "period_end": end_date,
    }


@router.get("/chart-of-accounts")
def list_chart_of_accounts(only_active: bool = True):
    """Return chart of accounts codes for selection in UI."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        query = """
            SELECT account_code, account_name, account_type, parent_account,
                   is_header_account, is_active, normal_balance
            FROM chart_of_accounts
        """
        params = []
        if only_active:
            query += " WHERE is_active IS DISTINCT FROM FALSE"
        query += " ORDER BY account_code"

        cur.execute(query, params)
        rows = cur.fetchall()
        return [
            {
                "account_code": r[0],
                "account_name": r[1],
                "account_type": r[2],
                "parent_account": r[3],
                "is_header_account": r[4],
                "is_active": r[5],
                "normal_balance": r[6],
            }
            for r in rows
            if r[0]
        ]
    finally:
        cur.close()
        conn.close()


@router.get("/reports/profit-loss")
def get_profit_loss_report(
    start_date: Optional[date] = None, end_date: Optional[date] = None
):
    """Generate Profit & Loss report"""
    conn = get_connection()
    cur = conn.cursor()

    # Default to current year
    if start_date is None:
        start_date = date(datetime.now().year, 1, 1)
    if end_date is None:
        end_date = date.today()

    # Revenue breakdown
    cur.execute(
        """
        SELECT
            COUNT(*) as charter_count,
            SUM(total_amount_due) as total_revenue,
            SUM(gst) as gst_collected
        FROM charters
        WHERE charter_date >= %s AND charter_date <= %s
    """,
        (start_date, end_date),
    )

    revenue_row = cur.fetchone()
    revenue = {
        "charter_count": revenue_row[0] or 0,
        "total_revenue": float(revenue_row[1]) if revenue_row[1] else 0.0,
        "gst_collected": float(revenue_row[2]) if revenue_row[2] else 0.0,
    }

    # Expense breakdown by category
    cur.execute(
        """
        SELECT
            category,
            COUNT(*) as count,
            SUM(amount) as total,
            SUM(COALESCE(gst_amount, 0)) as gst
        FROM receipts
        WHERE receipt_date >= %s AND receipt_date <= %s
        AND category != 'personal'
        GROUP BY category
        ORDER BY total DESC
    """,
        (start_date, end_date),
    )

    expenses = []
    total_expenses = 0
    total_gst_paid = 0

    for row in cur.fetchall():
        amount = float(row[2]) if row[2] else 0.0
        gst = float(row[3]) if row[3] else 0.0
        total_expenses += amount
        total_gst_paid += gst

        expenses.append(
            {
                "category": row[0] or "Uncategorized",
                "count": row[1],
                "amount": amount,
                "gst": gst,
            }
        )

    net_profit = revenue["total_revenue"] - total_expenses

    cur.close()
    conn.close()

    return {
        "period_start": start_date,
        "period_end": end_date,
        "revenue": revenue,
        "expenses": expenses,
        "total_expenses": total_expenses,
        "total_gst_paid": total_gst_paid,
        "net_profit": net_profit,
        "net_gst_owed": revenue["gst_collected"] - total_gst_paid,
    }


@router.get("/reports/cash-flow")
def get_cash_flow_report(
    start_date: Optional[date] = None, end_date: Optional[date] = None
):
    """Generate Cash Flow report"""
    conn = get_connection()
    cur = conn.cursor()

    if start_date is None:
        start_date = date(datetime.now().year, 1, 1)
    if end_date is None:
        end_date = date.today()

    # Cash In (payments received)
    cur.execute(
        """
        SELECT
            COALESCE(SUM(amount), 0) as total_in
        FROM payments
        WHERE payment_date >= %s AND payment_date <= %s
    """,
        (start_date, end_date),
    )
    cash_in = float(cur.fetchone()[0] or 0)

    # Cash Out (receipts paid)
    cur.execute(
        """
        SELECT
            COALESCE(SUM(gross_amount + COALESCE(gst_amount, 0)), 0) as total_out
        FROM receipts
        WHERE receipt_date >= %s AND receipt_date <= %s
        AND category != 'personal'
    """,
        (start_date, end_date),
    )
    cash_out = float(cur.fetchone()[0] or 0)

    net_cash_flow = cash_in - cash_out

    cur.close()
    conn.close()

    return {
        "period_start": start_date,
        "period_end": end_date,
        "cash_in": cash_in,
        "cash_out": cash_out,
        "net_cash_flow": net_cash_flow,
    }


@router.get("/reports/ar-aging")
def get_ar_aging_report():
    """Generate Accounts Receivable Aging report"""
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT
            i.invoice_id,
            i.invoice_number,
            COALESCE(c.customer_name, cust.company_name, cust.first_name || ' ' || cust.last_name) as customer_name,
            i.invoice_date,
            i.due_date,
            (i.amount + i.gst) as total,
            CURRENT_DATE - i.due_date as days_overdue
        FROM invoices i
        LEFT JOIN charters c ON i.charter_id = c.charter_id
        LEFT JOIN customers cust ON i.customer_id = cust.customer_id
        WHERE i.paid_date IS NULL
        ORDER BY days_overdue DESC
    """
    )

    aging = {
        "current": [],
        "1_30_days": [],
        "31_60_days": [],
        "61_90_days": [],
        "over_90_days": [],
    }

    totals = {
        "current": 0.0,
        "1_30_days": 0.0,
        "31_60_days": 0.0,
        "61_90_days": 0.0,
        "over_90_days": 0.0,
    }

    for row in cur.fetchall():
        invoice = {
            "invoice_id": row[0],
            "invoice_number": row[1],
            "customer_name": row[2],
            "invoice_date": row[3],
            "due_date": row[4],
            "amount": float(row[5]) if row[5] else 0.0,
            "days_overdue": row[6],
        }

        amount = invoice["amount"]
        days = invoice["days_overdue"]

        if days < 0:
            aging["current"].append(invoice)
            totals["current"] += amount
        elif days <= 30:
            aging["1_30_days"].append(invoice)
            totals["1_30_days"] += amount
        elif days <= 60:
            aging["31_60_days"].append(invoice)
            totals["31_60_days"] += amount
        elif days <= 90:
            aging["61_90_days"].append(invoice)
            totals["61_90_days"] += amount
        else:
            aging["over_90_days"].append(invoice)
            totals["over_90_days"] += amount

    cur.close()
    conn.close()

    return {
        "aging": aging,
        "totals": totals,
        "grand_total": sum(totals.values()),
    }
