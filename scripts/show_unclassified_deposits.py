#!/usr/bin/env python3
"""Show what transactions are being categorized as 'unclassified deposit'."""

import psycopg2

conn = psycopg2.connect(
    host="localhost",
    database="almsdata",
    user="postgres",
    password="***REMOVED***"
)

cur = conn.cursor()

# Get credit transactions that would be "unclassified"
cur.execute("""
    SELECT 
        bt.transaction_date,
        bt.account_number,
        bt.description,
        bt.credit_amount
    FROM banking_transactions bt
    WHERE bt.credit_amount > 0
      AND NOT EXISTS (
          SELECT 1 FROM receipts r 
          WHERE r.banking_transaction_id = bt.transaction_id
      )
      AND bt.description NOT ILIKE '%e-transfer%'
      AND bt.description NOT ILIKE '%email transfer%'
      AND bt.description NOT ILIKE '%interac%'
      AND bt.description NOT ILIKE '%square%'
      AND bt.description NOT ILIKE '%paypal%'
      AND bt.description NOT ILIKE '%stripe%'
      AND bt.description NOT ILIKE '%interest%'
      AND bt.description NOT ILIKE '%nsf%'
      AND bt.description NOT ILIKE '%insufficient%'
      AND bt.description NOT ILIKE '%loan%'
      AND bt.description NOT ILIKE '%transfer%'
      AND bt.description NOT ILIKE '%refund%'
      AND bt.description NOT ILIKE '%return%'
    ORDER BY bt.transaction_date DESC
    LIMIT 30
""")

transactions = cur.fetchall()

print("=" * 100)
print("TRANSACTIONS CATEGORIZED AS 'UNCLASSIFIED DEPOSIT' (Sample of 30 most recent)")
print("=" * 100)
print(f"\nDate         | Account      | Amount       | Description")
print("-" * 100)

for date, account, desc, amount in transactions:
    print(f"{date} | {account:12s} | ${amount:10.2f} | {desc[:70]}")

# Get count and breakdown by year
print("\n" + "=" * 100)
print("UNCLASSIFIED DEPOSITS BY YEAR")
print("=" * 100)

cur.execute("""
    SELECT 
        EXTRACT(YEAR FROM bt.transaction_date) as year,
        COUNT(*) as count,
        SUM(bt.credit_amount) as total_amount
    FROM banking_transactions bt
    WHERE bt.credit_amount > 0
      AND NOT EXISTS (
          SELECT 1 FROM receipts r 
          WHERE r.banking_transaction_id = bt.transaction_id
      )
      AND bt.description NOT ILIKE '%e-transfer%'
      AND bt.description NOT ILIKE '%email transfer%'
      AND bt.description NOT ILIKE '%interac%'
      AND bt.description NOT ILIKE '%square%'
      AND bt.description NOT ILIKE '%paypal%'
      AND bt.description NOT ILIKE '%stripe%'
      AND bt.description NOT ILIKE '%interest%'
      AND bt.description NOT ILIKE '%nsf%'
      AND bt.description NOT ILIKE '%insufficient%'
      AND bt.description NOT ILIKE '%loan%'
      AND bt.description NOT ILIKE '%transfer%'
      AND bt.description NOT ILIKE '%refund%'
      AND bt.description NOT ILIKE '%return%'
    GROUP BY year
    ORDER BY year DESC
""")

print(f"\nYear | Count    | Total Amount")
print("-" * 40)
for year, count, amount in cur.fetchall():
    print(f"{int(year)} | {count:8,d} | ${amount:12,.2f}")

# Get unique description patterns
print("\n" + "=" * 100)
print("COMMON DESCRIPTION PATTERNS (first word/type)")
print("=" * 100)

cur.execute("""
    SELECT 
        SPLIT_PART(bt.description, ' ', 1) as first_word,
        COUNT(*) as count,
        SUM(bt.credit_amount) as total_amount
    FROM banking_transactions bt
    WHERE bt.credit_amount > 0
      AND NOT EXISTS (
          SELECT 1 FROM receipts r 
          WHERE r.banking_transaction_id = bt.transaction_id
      )
      AND bt.description NOT ILIKE '%e-transfer%'
      AND bt.description NOT ILIKE '%email transfer%'
      AND bt.description NOT ILIKE '%interac%'
      AND bt.description NOT ILIKE '%square%'
      AND bt.description NOT ILIKE '%paypal%'
      AND bt.description NOT ILIKE '%stripe%'
      AND bt.description NOT ILIKE '%interest%'
      AND bt.description NOT ILIKE '%nsf%'
      AND bt.description NOT ILIKE '%insufficient%'
      AND bt.description NOT ILIKE '%loan%'
      AND bt.description NOT ILIKE '%transfer%'
      AND bt.description NOT ILIKE '%refund%'
      AND bt.description NOT ILIKE '%return%'
    GROUP BY first_word
    ORDER BY count DESC
    LIMIT 20
""")

print(f"\nPattern       | Count    | Total Amount")
print("-" * 50)
for pattern, count, amount in cur.fetchall():
    print(f"{pattern[:12]:12s} | {count:8,d} | ${amount:12,.2f}")

cur.close()
conn.close()
