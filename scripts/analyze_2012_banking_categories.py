#!/usr/bin/env python3
"""Analyze 2012 banking categories to see why audit showed zero."""
import os
import psycopg2

conn = psycopg2.connect(
    host=os.environ.get('DB_HOST', 'localhost'),
    database=os.environ.get('DB_NAME', 'almsdata'),
    user=os.environ.get('DB_USER', 'postgres'),
    password=os.environ.get('DB_PASSWORD', '***REDACTED***'),
)
cur = conn.cursor()

print("=== 2012 Banking Transaction Categories ===")
cur.execute("""
    SELECT 
        category,
        COUNT(*) as count,
        SUM(CASE WHEN debit_amount IS NOT NULL THEN debit_amount ELSE 0 END) as total_debits,
        SUM(CASE WHEN credit_amount IS NOT NULL THEN credit_amount ELSE 0 END) as total_credits
    FROM banking_transactions
    WHERE transaction_date BETWEEN '2012-01-01' AND '2012-12-31'
    GROUP BY category
    ORDER BY count DESC
""")
print(f"{'Category':<30} {'Count':>7} {'Debits':>14} {'Credits':>14}")
print("-" * 75)
for row in cur.fetchall():
    cat = row[0] or '(NULL)'
    print(f"{cat:<30} {row[1]:>7,} ${row[2]:>12,.2f} ${row[3]:>12,.2f}")

print("\n=== Sample 2012 Transactions (first 10) ===")
cur.execute("""
    SELECT transaction_id, transaction_date, description, debit_amount, credit_amount, category
    FROM banking_transactions
    WHERE transaction_date BETWEEN '2012-01-01' AND '2012-12-31'
    ORDER BY transaction_date, transaction_id
    LIMIT 10
""")
for row in cur.fetchall():
    desc = (row[2][:50] + '...') if row[2] and len(row[2]) > 50 else (row[2] or '')
    debit = f"${row[3]:,.2f}" if row[3] else "-"
    credit = f"${row[4]:,.2f}" if row[4] else "-"
    cat = row[5] or '(null)'
    print(f"{row[0]:>6} {row[1]} {debit:>12} {credit:>12} {cat:<20} {desc}")

print("\n=== Checking description patterns for withdrawals ===")
cur.execute("""
    SELECT 
        COUNT(*) as withdrawal_count,
        SUM(debit_amount) as total
    FROM banking_transactions
    WHERE transaction_date BETWEEN '2012-01-01' AND '2012-12-31'
      AND (
           LOWER(description) LIKE '%withdrawal%'
        OR LOWER(description) LIKE '%atm%'
        OR LOWER(description) LIKE '%cash%'
      )
""")
row = cur.fetchone()
print(f"Transactions with withdrawal/ATM/cash keywords: {row[0]:,}")
print(f"Total amount: ${row[1]:,.2f}" if row[1] else "Total amount: $0.00")

print("\n=== Checking description patterns for POS ===")
cur.execute("""
    SELECT 
        COUNT(*) as pos_count,
        SUM(debit_amount) as total
    FROM banking_transactions
    WHERE transaction_date BETWEEN '2012-01-01' AND '2012-12-31'
      AND (
           LOWER(description) LIKE '%pos%'
        OR LOWER(description) LIKE '%point of sale%'
        OR LOWER(description) LIKE '%purchase%'
      )
""")
row = cur.fetchone()
print(f"Transactions with POS/purchase keywords: {row[0]:,}")
print(f"Total amount: ${row[1]:,.2f}" if row[1] else "Total amount: $0.00")

cur.close()
conn.close()
