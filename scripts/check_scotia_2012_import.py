#!/usr/bin/env python
"""Check what was imported for Scotia 2012."""
import psycopg2
import os

conn = psycopg2.connect(
    host=os.environ.get('DB_HOST', 'localhost'),
    database=os.environ.get('DB_NAME', 'almsdata'),
    user=os.environ.get('DB_USER', 'postgres'),
    password=os.environ.get('DB_PASSWORD', '***REMOVED***')
)
cur = conn.cursor()

# Overall stats
cur.execute("""
    SELECT 
        COUNT(*) as total,
        MIN(transaction_date) as first_date,
        MAX(transaction_date) as last_date,
        COUNT(CASE WHEN balance IS NULL THEN 1 END) as null_balances,
        COUNT(CASE WHEN balance IS NOT NULL THEN 1 END) as has_balance
    FROM banking_transactions
    WHERE account_number = '903990106011'
    AND EXTRACT(YEAR FROM transaction_date) = 2012
""")

stats = cur.fetchone()
print(f"2012 Scotia Import:")
print(f"  Total records: {stats[0]}")
print(f"  Date range: {stats[1]} to {stats[2]}")
print(f"  NULL balances: {stats[3]} ({stats[3]/stats[0]*100:.1f}%)")
print(f"  Has balance: {stats[4]} ({stats[4]/stats[0]*100:.1f}%)")

# First and last transactions
print("\nFirst 5 transactions:")
cur.execute("""
    SELECT transaction_date, description, debit_amount, credit_amount, balance
    FROM banking_transactions
    WHERE account_number = '903990106011'
    AND EXTRACT(YEAR FROM transaction_date) = 2012
    ORDER BY transaction_date, transaction_id
    LIMIT 5
""")

for row in cur.fetchall():
    date, desc, debit, credit, balance = row
    print(f"  {date} | {desc[:40]:40} | Debit: {debit or 'NULL':>10} | Credit: {credit or 'NULL':>10} | Balance: {balance or 'NULL'}")

print("\nLast 5 transactions:")
cur.execute("""
    SELECT transaction_date, description, debit_amount, credit_amount, balance
    FROM banking_transactions
    WHERE account_number = '903990106011'
    AND EXTRACT(YEAR FROM transaction_date) = 2012
    ORDER BY transaction_date DESC, transaction_id DESC
    LIMIT 5
""")

for row in cur.fetchall():
    date, desc, debit, credit, balance = row
    print(f"  {date} | {desc[:40]:40} | Debit: {debit or 'NULL':>10} | Credit: {credit or 'NULL':>10} | Balance: {balance or 'NULL'}")

# Check if we have any specific dates
print("\nLooking for opening (2012-02-01) and closing (2012-12-31):")
cur.execute("""
    SELECT transaction_date, description, balance
    FROM banking_transactions
    WHERE account_number = '903990106011'
    AND transaction_date IN ('2012-02-01', '2012-12-31')
    ORDER BY transaction_date
""")

for row in cur.fetchall():
    print(f"  {row[0]}: {row[1][:50]} - Balance: {row[2] or 'NULL'}")

cur.close()
conn.close()
