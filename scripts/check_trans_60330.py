#!/usr/bin/env python3
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

cur.execute("SELECT transaction_id, transaction_date, description, debit_amount, credit_amount, category, check_number, check_recipient, verified, locked FROM banking_transactions WHERE transaction_id = 60330")
result = cur.fetchone()
if result:
    tid, date, desc, debit, credit, cat, check_num, check_recip, verified, locked = result
    print("Transaction 60330:")
    print(f"  Date: {date}")
    print(f"  Description: {desc}")
    print(f"  Amount: ${abs(debit or credit):,.2f} ({'DEBIT' if debit else 'CREDIT'})")
    print(f"  Category: {cat}")
    print(f"  Check Number: {check_num}")
    print(f"  Check Recipient: {check_recip}")
    print(f"  Verified: {verified}")
    print(f"  Locked: {locked}")

cur.close()
conn.close()
