#!/usr/bin/env python3
"""Compare CIBC 2012 statement balances to database."""

import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REMOVED***'
)
cur = conn.cursor()

# Get first transaction of 2012
cur.execute("""
    SELECT transaction_date, description, balance
    FROM banking_transactions
    WHERE account_number='0228362'
      AND transaction_date >= '2012-01-01'
      AND transaction_date < '2012-02-01'
    ORDER BY transaction_date, transaction_id
    LIMIT 1;
""")
first_txn = cur.fetchone()
print("First CIBC 2012 transaction:")
if first_txn:
    print(f"  Date: {first_txn[0]}")
    print(f"  Description: {first_txn[1]}")
    print(f"  Balance: ${first_txn[2]:.2f}" if first_txn[2] else "  Balance: NULL")

# Get last transaction of 2012
cur.execute("""
    SELECT transaction_date, description, balance
    FROM banking_transactions
    WHERE account_number='0228362'
      AND transaction_date >= '2012-01-01'
      AND transaction_date < '2013-01-01'
    ORDER BY transaction_date DESC, transaction_id DESC
    LIMIT 1;
""")
last_txn = cur.fetchone()
print("\nLast CIBC 2012 transaction:")
if last_txn:
    print(f"  Date: {last_txn[0]}")
    print(f"  Description: {last_txn[1]}")
    print(f"  Balance: ${last_txn[2]:.2f}" if last_txn[2] else "  Balance: NULL")

# Get totals
cur.execute("""
    WITH year_txns AS (
        SELECT * FROM banking_transactions
        WHERE account_number='0228362'
          AND transaction_date >= '2012-01-01'
          AND transaction_date < '2013-01-01'
    )
    SELECT COUNT(*) as txn_count,
           COALESCE(SUM(debit_amount), 0) as total_debits,
           COALESCE(SUM(credit_amount), 0) as total_credits
    FROM year_txns;
""")
result = cur.fetchone()
print(f"\nCIBC 2012 Database Totals:")
print(f"  Transaction count: {result[0]:,}")
print(f"  Total debits: ${result[1]:,.2f}")
print(f"  Total credits: ${result[2]:,.2f}")

print(f"\nCIBC 2012 Statement Totals (from PDF):")
print(f"  Opening Jan 1: $7,177.34")
print(f"  Closing Dec 31: $21.21")
print(f"  ⚠️  NOTE: Statement debits/credits for full year not yet extracted")

conn.close()
