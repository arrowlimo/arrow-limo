#!/usr/bin/env python3
import psycopg2
import os
from decimal import Decimal

conn = psycopg2.connect(
    host=os.environ.get("DB_HOST", "localhost"),
    database=os.environ.get("DB_NAME", "almsdata"),
    user=os.environ.get("DB_USER", "postgres"),
    password=os.environ.get("DB_PASSWORD", "***REDACTED***")
)
cur = conn.cursor()

print("Banking Transactions 69282 and 69587:")
print()

cur.execute("""
    SELECT transaction_id, description, debit_amount, credit_amount, balance
    FROM banking_transactions
    WHERE transaction_id IN (69282, 69587)
    ORDER BY transaction_id
""")

for row in cur.fetchall():
    tx_id, desc, debit, credit, balance = row
    debit = debit or Decimal('0')
    credit = credit or Decimal('0')
    balance = balance or Decimal('0')
    
    print(f"TX {tx_id}: {desc}")
    print(f"  Debit:  ${debit:,.2f}")
    print(f"  Credit: ${credit:,.2f}")
    print(f"  Balance: ${balance:,.2f}")
    print()

conn.close()
