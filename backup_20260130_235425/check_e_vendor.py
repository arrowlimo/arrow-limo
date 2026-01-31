#!/usr/bin/env python3
"""Check what the 'E' vendor was."""

import psycopg2
import os

conn = psycopg2.connect(
    host="localhost",
    database="almsdata",
    user="postgres",
    password=os.environ.get('DB_PASSWORD')
)
cur = conn.cursor()

# Find the "E" transaction in the backup
cur.execute("""
    SELECT 
        transaction_id,
        transaction_date,
        description,
        debit_amount,
        credit_amount,
        vendor_extracted
    FROM banking_transactions_typo_fix_20251206_230713
    WHERE vendor_extracted = 'E'
    LIMIT 10;
""")

print("\n=== ORIGINAL 'E' TRANSACTION ===\n")
for row in cur.fetchall():
    txn_id, date, desc, debit, credit, vendor = row
    amount = debit if debit else credit
    print(f"TX {txn_id:5} | {date} | ${amount:8.2f} | Vendor: '{vendor}'")
    print(f"         Full description: {desc}\n")

conn.close()
