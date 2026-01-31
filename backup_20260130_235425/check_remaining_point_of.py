#!/usr/bin/env python3
"""Check remaining POINT OF receipts missing USD tracking."""

import psycopg2

conn = psycopg2.connect(
    host="localhost",
    database="almsdata",
    user="postgres",
    password="***REDACTED***"
)
cur = conn.cursor()

cur.execute("""
    SELECT r.receipt_id, r.vendor_name, r.gross_amount, r.description,
           bt.description as banking_desc
    FROM receipts r
    JOIN banking_receipt_matching_ledger brml ON r.receipt_id = brml.receipt_id
    JOIN banking_transactions bt ON brml.banking_transaction_id = bt.transaction_id
    WHERE r.vendor_name = 'POINT OF'
      AND bt.description LIKE '%INTL%'
      AND (r.description IS NULL OR (r.description NOT LIKE '%@%' AND r.description NOT LIKE '%USD%'))
""")

results = cur.fetchall()
print(f'Found {len(results)} POINT OF receipts still missing USD tracking:')
for r in results:
    print(f'  {r[0]} | {r[1]} | ${r[2]:.2f} | {r[3]}')
    print(f'    Banking: {r[4][:80]}')

cur.close()
conn.close()
