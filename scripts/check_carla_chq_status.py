#!/usr/bin/env python3
"""
Check if Carla Metuier CHQ 203 receipt is properly linked to the correct banking transaction.
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
print("CARLA METUIER CHQ 203 STATUS CHECK")
print("=" * 80)

# Check receipts for Metuier
print("\n1. RECEIPTS:")
cur.execute("""
    SELECT receipt_id, receipt_date, vendor_name, gross_amount, 
           banking_transaction_id, mapped_bank_account_id
    FROM receipts
    WHERE vendor_name ILIKE %s OR vendor_name ILIKE %s
    ORDER BY receipt_id
""", ('%METUI%', '%METIRI%'))

receipts = cur.fetchall()
print(f"   Found {len(receipts)} receipt(s)")
for r_id, date, vendor, amount, bt_id, bank in receipts:
    bank_name = 'CIBC' if bank == 1 else ('SCOTIA' if bank == 2 else 'Unknown')
    print(f"   Receipt {r_id} | {date} | {vendor} | ${amount:,.2f} | TX {bt_id} | {bank_name}")

# Check banking transactions for CHQ 203 $1,771.12
print("\n2. BANKING TRANSACTIONS (CHQ 203, $1,771.12):")
cur.execute("""
    SELECT transaction_id, transaction_date, 
           CASE WHEN bank_id = 1 THEN 'CIBC' WHEN bank_id = 2 THEN 'SCOTIA' ELSE 'Unknown' END as bank,
           debit_amount, credit_amount, description, reconciliation_status
    FROM banking_transactions
    WHERE (description ILIKE %s OR description ILIKE %s)
      OR (description LIKE %s AND (debit_amount = 1771.12 OR credit_amount = 1771.12))
    ORDER BY transaction_date
""", ('%METUI%', '%METIRI%', '%203%'))

transactions = cur.fetchall()
print(f"   Found {len(transactions)} transaction(s)")
for tx_id, date, bank, debit, credit, desc, status in transactions:
    amount = debit if debit else credit
    tx_type = 'DEBIT' if debit else 'CREDIT'
    status_display = f'[{status}]' if status else ''
    print(f"   TX {tx_id:6d} | {date} | {bank:7} | ${amount:>10,.2f} {tx_type:6} | {desc[:50]:<50} {status_display}")

# Check the link
print("\n" + "=" * 80)
print("3. LINK STATUS:")
print("=" * 80)

if receipts:
    for receipt in receipts:
        r_id, r_date, r_vendor, r_amount, receipt_tx_id, r_bank = receipt
        
        cur.execute("""
            SELECT transaction_id, description, reconciliation_status,
                   CASE WHEN debit_amount IS NOT NULL THEN 'DEBIT' ELSE 'CREDIT' END as type,
                   debit_amount, credit_amount
            FROM banking_transactions
            WHERE transaction_id = %s
        """, (receipt_tx_id,))
        
        tx = cur.fetchone()
        if tx:
            tx_id, desc, status, tx_type, debit, credit = tx
            amount = debit if debit else credit
            
            print(f"\nReceipt {r_id} (${r_amount:,.2f}) is linked to:")
            print(f"  TX {tx_id} | {tx_type} | ${amount:,.2f}")
            print(f"  Description: {desc}")
            print(f"  Status: {status or 'ACTIVE'}")
            
            if status == 'QB_DUPLICATE':
                print(f"\n  ❌ PROBLEM: Linked to QB duplicate!")
                print(f"  Should link to TX 56865 (real bank DEBIT)")
                print(f"\n  FIX: UPDATE receipts SET banking_transaction_id = 56865")
                print(f"       WHERE receipt_id = {r_id}")
            elif tx_type == 'DEBIT':
                print(f"\n  ✅ OK: Linked to real bank DEBIT transaction")
            else:
                print(f"\n  ⚠️  WARNING: Linked to CREDIT transaction (unusual for expense receipt)")
else:
    print("\n❌ NO RECEIPTS FOUND for Metuier/Metirier")
    print("\nExpected: Receipt 139332 for CHQ 203 Carla Metuier $1,771.12")

cur.close()
conn.close()
