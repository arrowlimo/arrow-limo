#!/usr/bin/env python3
"""Check the actual banking transactions for the two large CHEQUEs."""

import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()
conn = psycopg2.connect(
    host=os.environ.get("DB_HOST", "localhost"),
    database=os.environ.get("DB_NAME", "almsdata"),
    user=os.environ.get("DB_USER", "postgres"),
    password=os.environ.get("DB_PASSWORD", "***REDACTED***")
)
cur = conn.cursor()

print("=" * 100)
print("BANKING TRANSACTIONS FOR THE TWO LARGE CHEQUES")
print("=" * 100 + "\n")

for trans_id in [60389, 60330]:
    cur.execute("""
        SELECT transaction_id, transaction_date, description, debit_amount, credit_amount, 
               source, verified, locked, banking_account_id, memo
        FROM banking_transactions
        WHERE transaction_id = %s
    """, (trans_id,))
    
    result = cur.fetchone()
    if result:
        tid, date, desc, debit, credit, source, verified, locked, acct_id, memo = result
        amount = debit or credit
        print(f"Transaction ID: {tid}")
        print(f"Date: {date}")
        print(f"Description: {desc}")
        print(f"Amount: ${abs(amount):,.2f} ({'DEBIT' if debit else 'CREDIT'})")
        print(f"Source: {source}")
        print(f"Verified: {verified}")
        print(f"Locked: {locked}")
        print(f"Banking Account ID: {acct_id}")
        print(f"Memo: {memo}")
        print()

cur.close()
conn.close()

print("✅ Analysis complete")
