#!/usr/bin/env python3
"""
Show all transactions on October 1, 2012.
"""

import psycopg2
import os

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

print("=" * 80)
print("ALL TRANSACTIONS ON OCTOBER 1, 2012")
print("=" * 80)

cur.execute("""
    SELECT transaction_id, debit_amount, credit_amount, description,
           CASE WHEN bank_id = 1 THEN 'CIBC' WHEN bank_id = 2 THEN 'SCOTIA' ELSE 'Unknown' END as bank,
           reconciliation_status
    FROM banking_transactions
    WHERE transaction_date = '2012-10-01'
    ORDER BY transaction_id
""")

results = cur.fetchall()
print(f"\nFound {len(results)} transaction(s) on Oct 1, 2012:\n")

for tx_id, debit, credit, desc, bank, status in results:
    amount = debit if debit else credit
    tx_type = 'DEBIT' if debit else 'CREDIT'
    
    # Check for receipt
    cur.execute("""
        SELECT receipt_id, vendor_name
        FROM receipts
        WHERE banking_transaction_id = %s
    """, (tx_id,))
    
    receipt = cur.fetchone()
    receipt_info = f"Receipt {receipt[0]} ({receipt[1]})" if receipt else "NO RECEIPT"
    
    status_display = f"[{status}]" if status else ""
    print(f"TX {tx_id:6d} | {bank:7} | {tx_type:6} | ${amount:>10,.2f} | {receipt_info:35} | {desc[:50]} {status_display}")

cur.close()
conn.close()
