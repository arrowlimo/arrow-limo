#!/usr/bin/env python3
"""
Verify Oct 1, 2012 transactions are REAL bank transactions, not QuickBooks duplicates.
Scotia Bank should be fully matched - if no receipt, probably QB duplicate.
CIBC 8362 not fully verified - might be real unmatched transactions.
"""

import psycopg2
import os

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

print("=" * 80)
print("OCT 1, 2012 - VERIFY REAL BANK TRANSACTIONS VS QB DUPLICATES")
print("=" * 80)

# The 19 transactions without receipts
tx_ids = [57852, 57853, 69387, 69388, 69389, 69390, 69391, 69392, 69393, 
          69394, 69395, 69396, 69397, 69398, 69399, 69400, 69401, 69402, 69403]

print(f"\nChecking {len(tx_ids)} transactions...\n")

cibc_transactions = []
scotia_transactions = []

for tx_id in tx_ids:
    # Get transaction details
    cur.execute("""
        SELECT transaction_date, debit_amount, credit_amount, description,
               bank_id,
               CASE WHEN bank_id = 1 THEN 'CIBC' WHEN bank_id = 2 THEN 'SCOTIA' ELSE 'Unknown' END as bank
        FROM banking_transactions
        WHERE transaction_id = %s
    """, (tx_id,))
    
    tx = cur.fetchone()
    if not tx:
        continue
    
    date, debit, credit, desc, bank_id, bank = tx
    amount = debit if debit else credit
    tx_type = 'DEBIT' if debit else 'CREDIT'
    
    # Look for duplicate transactions (same date, amount, description pattern)
    cur.execute("""
        SELECT transaction_id, description, 
               CASE WHEN bank_id = 1 THEN 'CIBC' WHEN bank_id = 2 THEN 'SCOTIA' ELSE 'Unknown' END as bank,
               reconciliation_status
        FROM banking_transactions
        WHERE transaction_date = %s
          AND ((debit_amount = %s AND %s IS NOT NULL) OR (credit_amount = %s AND %s IS NULL))
          AND transaction_id != %s
        ORDER BY transaction_id
    """, (date, amount, debit, amount, debit, tx_id))
    
    duplicates = cur.fetchall()
    
    # Check for receipt
    cur.execute("""
        SELECT receipt_id, vendor_name
        FROM receipts
        WHERE banking_transaction_id = %s
    """, (tx_id,))
    
    receipt = cur.fetchone()
    
    tx_data = {
        'tx_id': tx_id,
        'bank': bank,
        'bank_id': bank_id,
        'type': tx_type,
        'amount': amount,
        'desc': desc,
        'duplicates': duplicates,
        'has_receipt': receipt is not None
    }
    
    if bank_id == 1:
        cibc_transactions.append(tx_data)
    elif bank_id == 2:
        scotia_transactions.append(tx_data)

# Report Scotia Bank (should all be matched already)
print("=" * 80)
print("SCOTIA BANK (Should be fully matched - no receipt = probably QB duplicate)")
print("=" * 80)

for t in scotia_transactions:
    status = "✅ HAS RECEIPT" if t['has_receipt'] else "❌ NO RECEIPT (SUSPECT QB DUPLICATE)"
    print(f"\nTX {t['tx_id']:6d} | {t['type']:6} | ${t['amount']:>10,.2f} | {status}")
    print(f"  Description: {t['desc'][:60]}")
    
    if t['duplicates']:
        print(f"  ⚠️  DUPLICATES FOUND:")
        for dup_id, dup_desc, dup_bank, dup_status in t['duplicates']:
            print(f"     TX {dup_id:6d} | {dup_bank:7} | {dup_desc[:50]} [{dup_status or 'ACTIVE'}]")

# Report CIBC (not fully verified)
print("\n\n" + "=" * 80)
print("CIBC 8362 (Not fully verified - might be real unmatched transactions)")
print("=" * 80)

for t in cibc_transactions:
    status = "✅ HAS RECEIPT" if t['has_receipt'] else "❓ NO RECEIPT (Might be real - CIBC not fully verified)"
    print(f"\nTX {t['tx_id']:6d} | {t['type']:6} | ${t['amount']:>10,.2f} | {status}")
    print(f"  Description: {t['desc'][:60]}")
    
    if t['duplicates']:
        print(f"  ⚠️  DUPLICATES FOUND:")
        for dup_id, dup_desc, dup_bank, dup_status in t['duplicates']:
            print(f"     TX {dup_id:6d} | {dup_bank:7} | {dup_desc[:50]} [{dup_status or 'ACTIVE'}]")

# Summary
print("\n\n" + "=" * 80)
print("SUMMARY")
print("=" * 80)
print(f"Scotia Bank transactions: {len(scotia_transactions)}")
print(f"  - With receipts: {sum(1 for t in scotia_transactions if t['has_receipt'])}")
print(f"  - WITHOUT receipts (SUSPECT QB DUPLICATES): {sum(1 for t in scotia_transactions if not t['has_receipt'])}")
print()
print(f"CIBC 8362 transactions: {len(cibc_transactions)}")
print(f"  - With receipts: {sum(1 for t in cibc_transactions if t['has_receipt'])}")
print(f"  - WITHOUT receipts (Might be real): {sum(1 for t in cibc_transactions if not t['has_receipt'])}")

cur.close()
conn.close()
