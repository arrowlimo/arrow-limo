#!/usr/bin/env python3
"""Query Scotia 2012 banking totals and balances."""

import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REDACTED***'
)
cur = conn.cursor()

# Get summary stats
cur.execute("""
    WITH year_txns AS (
        SELECT * FROM banking_transactions
        WHERE account_number='903990106011'
          AND transaction_date >= '2012-01-01'
          AND transaction_date < '2013-01-01'
    )
    SELECT MIN(transaction_date), MAX(transaction_date),
           COALESCE(SUM(debit_amount), 0),
           SUM(CASE WHEN debit_amount>0 THEN 1 ELSE 0 END),
           COALESCE(SUM(credit_amount), 0),
           SUM(CASE WHEN credit_amount>0 THEN 1 ELSE 0 END)
    FROM year_txns;
""")
result = cur.fetchone()
if result:
    first_date, last_date, total_debits, debit_count, total_credits, credit_count = result
    print(f"Scotia 2012 Summary:")
    print(f"  Date range: {first_date} to {last_date}")
    print(f"  Debits: ${total_debits:.2f} ({debit_count} transactions)")
    print(f"  Credits: ${total_credits:.2f} ({credit_count} transactions)")

# Get first transaction balance
cur.execute("""
    WITH year_txns AS (
        SELECT * FROM banking_transactions
        WHERE account_number='903990106011'
          AND transaction_date >= '2012-01-01'
          AND transaction_date < '2013-01-01'
    )
    SELECT transaction_date, balance
    FROM year_txns
    ORDER BY transaction_date, transaction_id
    LIMIT 1;
""")
result = cur.fetchone()
if result:
    print(f"\n  First transaction: {result[0]}")
    print(f"  Opening balance: ${result[1]:.2f}")

# Get last transaction balance
cur.execute("""
    WITH year_txns AS (
        SELECT * FROM banking_transactions
        WHERE account_number='903990106011'
          AND transaction_date >= '2012-01-01'
          AND transaction_date < '2013-01-01'
    )
    SELECT transaction_date, balance
    FROM year_txns
    ORDER BY transaction_date DESC, transaction_id DESC
    LIMIT 1;
""")
result = cur.fetchone()
if result:
    print(f"\n  Last transaction: {result[0]}")
    print(f"  Closing balance: ${result[1]:.2f}")

conn.close()
