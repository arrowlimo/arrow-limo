#!/usr/bin/env python3
"""Check if receipts linked to credit transactions have expense or revenue populated."""

import psycopg2

conn = psycopg2.connect(
    host="localhost",
    database="almsdata",
    user="postgres",
    password="***REDACTED***"
)

cur = conn.cursor()

print("=" * 80)
print("RECEIPTS LINKED TO CREDIT TRANSACTIONS - DATA ANALYSIS")
print("=" * 80)

# Check what's in expense/revenue columns for receipts linked to credits
cur.execute("""
    SELECT 
        CASE 
            WHEN r.expense > 0 AND (r.revenue IS NULL OR r.revenue = 0) THEN 'EXPENSE only'
            WHEN r.revenue > 0 AND (r.expense IS NULL OR r.expense = 0) THEN 'REVENUE only'
            WHEN r.expense > 0 AND r.revenue > 0 THEN 'BOTH (error?)'
            ELSE 'NEITHER'
        END as data_type,
        COUNT(*) as count,
        SUM(r.gross_amount) as total_gross,
        SUM(COALESCE(r.expense, 0)) as total_expense,
        SUM(COALESCE(r.revenue, 0)) as total_revenue
    FROM banking_transactions bt
    JOIN receipts r ON r.banking_transaction_id = bt.transaction_id
    WHERE bt.credit_amount > 0
    GROUP BY data_type
    ORDER BY data_type
""")

print("\nData Type          | Count    | Total Gross    | Total Expense  | Total Revenue")
print("-" * 90)
for data_type, count, gross, expense, revenue in cur.fetchall():
    print(f"{data_type:18s} | {count:8,d} | ${gross:13,.2f} | ${expense:13,.2f} | ${revenue:13,.2f}")

# Sample of receipts with EXPENSE on credit transactions
print("\n" + "=" * 80)
print("SAMPLE: Receipts with EXPENSE on CREDIT transactions (Money In)")
print("=" * 80)

cur.execute("""
    SELECT 
        r.receipt_date,
        r.vendor_name,
        r.expense,
        r.revenue,
        r.gross_amount,
        bt.credit_amount,
        bt.description,
        r.gl_account_code
    FROM banking_transactions bt
    JOIN receipts r ON r.banking_transaction_id = bt.transaction_id
    WHERE bt.credit_amount > 0
      AND r.expense > 0
      AND (r.revenue IS NULL OR r.revenue = 0)
    ORDER BY r.receipt_date DESC
    LIMIT 15
""")

print("\nDate       | Vendor                      | Expense    | Credit     | GL   | Bank Description")
print("-" * 120)
for date, vendor, expense, revenue, gross, credit, desc, gl in cur.fetchall():
    print(f"{date} | {vendor:27s} | ${expense:9.2f} | ${credit:9.2f} | {gl or 'None':4s} | {desc[:50]}")

# Check if these are NSF/reversal type transactions
print("\n" + "=" * 80)
print("CHECKING FOR NSF/REVERSAL PATTERNS")
print("=" * 80)

cur.execute("""
    SELECT 
        CASE 
            WHEN r.vendor_name ILIKE '%nsf%' OR bt.description ILIKE '%nsf%' THEN 'NSF Related'
            WHEN r.vendor_name ILIKE '%reversal%' OR bt.description ILIKE '%reversal%' THEN 'Reversal'
            WHEN r.vendor_name ILIKE '%return%' OR bt.description ILIKE '%return%' THEN 'Return'
            WHEN r.vendor_name ILIKE '%refund%' OR bt.description ILIKE '%refund%' THEN 'Refund'
            WHEN bt.description ILIKE '%transfer%' THEN 'Transfer'
            WHEN bt.description ILIKE '%deposit%' THEN 'Deposit'
            ELSE 'Other'
        END as transaction_category,
        COUNT(*) as count,
        SUM(r.expense) as total_expense,
        SUM(bt.credit_amount) as total_credit
    FROM banking_transactions bt
    JOIN receipts r ON r.banking_transaction_id = bt.transaction_id
    WHERE bt.credit_amount > 0
      AND r.expense > 0
      AND (r.revenue IS NULL OR r.revenue = 0)
    GROUP BY transaction_category
    ORDER BY count DESC
""")

print("\nCategory           | Count    | Total Expense  | Total Credit")
print("-" * 70)
for category, count, expense, credit in cur.fetchall():
    print(f"{category:18s} | {count:8,d} | ${expense:13,.2f} | ${credit:13,.2f}")

print("\n" + "=" * 80)

cur.close()
conn.close()
