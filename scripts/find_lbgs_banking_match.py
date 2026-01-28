#!/usr/bin/env python
"""Find banking match for LBG'S receipt."""
import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

print("\n" + "="*120)
print("RECEIPT: LBG'S")
print("="*120)
cur.execute("""
    SELECT receipt_id, receipt_date, gross_amount, vendor_name, description, 
           gl_account_code, banking_transaction_id, created_from_banking
    FROM receipts
    WHERE receipt_id = 67506
""")
r = cur.fetchone()
if r:
    receipt_id, receipt_date, gross_amount, vendor, desc, gl_code, banking_txn_id, created_from_banking = r
    print(f"  Receipt ID: {receipt_id}")
    print(f"  Date: {receipt_date}")
    print(f"  Amount: ${gross_amount:.2f}")
    print(f"  Vendor: {vendor}")
    print(f"  GL Code: {gl_code}")
    print(f"  Banking Txn ID: {banking_txn_id}")
    print(f"  Created from banking: {created_from_banking}")
    print()

print("\n" + "="*120)
print("BANKING MATCH DETAILS - Transaction ID 31788")
print("="*120)
cur.execute("""
    SELECT transaction_id, transaction_date, debit_amount, credit_amount, description, 
           vendor_extracted
    FROM banking_transactions
    WHERE transaction_id = 31788
""")
rows = cur.fetchall()
print(f"\n{len(rows)} banking transaction(s):\n")
for txn_id, txn_date, debit, credit, desc, vendor in rows:
    amount = debit if debit else credit
    print(f"  Transaction ID: {txn_id}")
    print(f"  Date: {txn_date}")
    print(f"  Amount: ${amount:.2f}")
    print(f"  Type: {'Debit' if debit else 'Credit'}")
    print(f"  Vendor: {vendor}")
    print(f"  Description: {desc}")
    print()

cur.close()
conn.close()
