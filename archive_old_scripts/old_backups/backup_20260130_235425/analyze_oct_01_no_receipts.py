#!/usr/bin/env python3
"""
Check the Oct 1, 2012 transactions that have NO RECEIPTS.
Determine if they're real bank transactions or QuickBooks duplicates.
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
print("OCTOBER 1, 2012 TRANSACTIONS - RECEIPT STATUS ANALYSIS")
print("=" * 80)

# Get all Oct 1, 2012 transactions
cur.execute("""
    SELECT transaction_id, debit_amount, credit_amount, description,
           CASE WHEN bank_id = 1 THEN 'CIBC' WHEN bank_id = 2 THEN 'SCOTIA' ELSE 'Unknown' END as bank,
           reconciliation_status
    FROM banking_transactions
    WHERE transaction_date = '2012-10-01'
    ORDER BY transaction_id
""")

transactions = cur.fetchall()

print(f"\nTotal transactions: {len(transactions)}")
print()

# Categorize
real_bank = []
qb_entries = []
unknown = []

for tx_id, debit, credit, desc, bank, status in transactions:
    amount = debit if debit else credit
    tx_type = 'DEBIT' if debit else 'CREDIT'
    
    # Check for receipt
    cur.execute("""
        SELECT receipt_id, vendor_name
        FROM receipts
        WHERE banking_transaction_id = %s
    """, (tx_id,))
    
    receipt = cur.fetchone()
    has_receipt = "YES" if receipt else "NO"
    
    # Determine type
    is_qb = (
        'Cheque Expense' in desc or
        status == 'QB_DUPLICATE'
    )
    
    is_real_bank = (
        bank in ('CIBC', 'SCOTIA') and
        not is_qb and
        status != 'QB_DUPLICATE'
    )
    
    row_data = {
        'tx_id': tx_id,
        'date': '2012-10-01',
        'bank': bank,
        'type': tx_type,
        'amount': amount,
        'desc': desc,
        'status': status,
        'receipt': has_receipt
    }
    
    if is_real_bank:
        real_bank.append(row_data)
    elif is_qb:
        qb_entries.append(row_data)
    else:
        unknown.append(row_data)

# Report real bank transactions without receipts
print("=" * 80)
print("1. REAL BANK TRANSACTIONS (Need receipts)")
print("=" * 80)

real_no_receipt = [t for t in real_bank if t['receipt'] == 'NO']
real_with_receipt = [t for t in real_bank if t['receipt'] == 'YES']

print(f"\nWith receipts: {len(real_with_receipt)}")
print(f"WITHOUT receipts: {len(real_no_receipt)}")

if real_no_receipt:
    print(f"\n⚠️ These NEED receipts created:")
    for t in real_no_receipt:
        print(f"  TX {t['tx_id']:6d} | {t['bank']:7} | {t['type']:6} | ${t['amount']:>10,.2f} | {t['desc'][:50]}")

# Report QB entries
print("\n\n" + "=" * 80)
print("2. QUICKBOOKS ENTRIES (Don't need receipts - accounting only)")
print("=" * 80)

print(f"\nTotal QB entries: {len(qb_entries)}")
if qb_entries:
    for t in qb_entries[:10]:
        print(f"  TX {t['tx_id']:6d} | {t['bank']:7} | {t['type']:6} | ${t['amount']:>10,.2f} | {t['desc'][:50]}")
    if len(qb_entries) > 10:
        print(f"  ... and {len(qb_entries) - 10} more")

# Report unknown
print("\n\n" + "=" * 80)
print("3. UNKNOWN SOURCE (Need investigation)")
print("=" * 80)

print(f"\nTotal unknown: {len(unknown)}")
if unknown:
    for t in unknown:
        print(f"  TX {t['tx_id']:6d} | {t['bank']:7} | {t['type']:6} | ${t['amount']:>10,.2f} | {t['desc'][:50]}")
        print(f"    Status: {t['status'] or 'None'} | Receipt: {t['receipt']}")

# Summary
print("\n\n" + "=" * 80)
print("SUMMARY")
print("=" * 80)
print(f"Real bank transactions needing receipts: {len(real_no_receipt)}")
print(f"QuickBooks entries (OK without receipts): {len(qb_entries)}")
print(f"Unknown/needs investigation: {len(unknown)}")

cur.close()
conn.close()
