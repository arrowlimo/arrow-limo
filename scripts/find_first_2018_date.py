#!/usr/bin/env python3
"""Find first banking transaction date in 2018 for CIBC 0228362."""

import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REDACTED***'
)

cur = conn.cursor()

# First check column names
cur.execute("""
    SELECT column_name 
    FROM information_schema.columns 
    WHERE table_name = 'banking_transactions' 
    ORDER BY ordinal_position
""")
cols = [row[0] for row in cur.fetchall()]
print(f"Banking transactions columns: {', '.join(cols)}\n")

# Find first 2018 date for CIBC account
cur.execute("""
    SELECT MIN(transaction_date) as first_date,
           COUNT(*) as transaction_count
    FROM banking_transactions 
    WHERE EXTRACT(YEAR FROM transaction_date) = 2018
    AND account_number LIKE '%8362'
""")
result = cur.fetchone()
print(f"First date in 2018 for CIBC 0228362: {result[0]}")
print(f"Total 2018 transactions: {result[1]}")

# Show first few transactions
cur.execute("""
    SELECT transaction_date, description, 
           COALESCE(credit_amount, 0) - COALESCE(debit_amount, 0) as net_amount
    FROM banking_transactions 
    WHERE EXTRACT(YEAR FROM transaction_date) = 2018
    AND account_number LIKE '%8362'
    ORDER BY transaction_date
    LIMIT 5
""")
print("\nFirst 5 transactions in 2018:")
for row in cur.fetchall():
    print(f"  {row[0]} | {row[1][:50]:50s} | ${row[2]:,.2f}")

cur.close()
conn.close()
