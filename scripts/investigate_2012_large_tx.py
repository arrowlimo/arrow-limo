#!/usr/bin/env python3
"""Investigate the two large 2012 transactions without check numbers."""

import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()
conn = psycopg2.connect(
    host=os.environ.get("DB_HOST", "localhost"),
    database=os.environ.get("DB_NAME", "almsdata"),
    user=os.environ.get("DB_USER", "postgres"),
    password=os.environ.get("DB_PASSWORD", "***REMOVED***")
)
cur = conn.cursor()

print("=" * 100)
print("INVESTIGATE TWO LARGE 2012 TRANSACTIONS WITHOUT CHECK NUMBERS")
print("=" * 100 + "\n")

for trans_id, vendor in [(60278, "Warehouse One"), (60316, "IFS Premium Finance")]:
    cur.execute("""
        SELECT transaction_id, transaction_date, description, 
               debit_amount, credit_amount, category, source_file, import_batch,
               verified, locked, memo, check_number, check_recipient
        FROM banking_transactions
        WHERE transaction_id = %s
    """, (trans_id,))
    
    result = cur.fetchone()
    if result:
        tid, date, desc, debit, credit, cat, src_file, batch, verified, locked, memo, check_num, check_recip = result
        amount = debit or credit
        
        print(f"\nTransaction {tid} - {vendor}")
        print("-" * 100)
        print(f"Date: {date}")
        print(f"Description: {desc}")
        print(f"Amount: ${amount:,.2f} ({'DEBIT' if debit else 'CREDIT'})")
        print(f"Category: {cat}")
        print(f"Source File: {src_file}")
        print(f"Import Batch: {batch}")
        print(f"Verified: {verified}")
        print(f"Locked: {locked}")
        print(f"Memo: {memo}")
        print(f"Check Number: {check_num}")
        print(f"Check Recipient: {check_recip}")
        
        # Check for linked receipts
        cur.execute("""
            SELECT receipt_id, vendor_name, gross_amount, description, gl_account_code
            FROM receipts
            WHERE banking_transaction_id = %s
        """, (trans_id,))
        
        receipts = cur.fetchall()
        if receipts:
            print(f"\n  Linked receipts ({len(receipts)}):")
            for r_id, r_vendor, r_amount, r_desc, r_gl in receipts:
                print(f"    Receipt {r_id}: {r_vendor} | ${r_amount:,.2f} | GL {r_gl}")
        else:
            print("\n  ❌ No linked receipts found")

cur.close()
conn.close()

print("\n✅ Analysis complete")
