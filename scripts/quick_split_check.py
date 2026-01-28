#!/usr/bin/env python3
"""
Quick check: Are multi-receipt banking TXs legitimate splits or duplicates?
"""
import psycopg2, os
from decimal import Decimal

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

# Sample the first problematic TX we identified
print("EXAMPLE: Banking TX #33094 (Aurora Premium Financing)")
print("="*70)

cur.execute("""
    SELECT receipt_id, vendor_name, gross_amount, is_split_receipt, 
           split_key, expense_account, description
    FROM receipts 
    WHERE banking_transaction_id = 33094
    ORDER BY receipt_id
""")

for r in cur.fetchall():
    print(f"\nReceipt #{r[0]}:")
    print(f"  Vendor: {r[1]}")
    print(f"  Amount: ${r[2]}")
    print(f"  Is Split: {r[3]}")
    print(f"  Split Key: {r[4]}")
    print(f"  Account: {r[5]}")
    print(f"  Description: {r[6]}")

cur.execute("SELECT transaction_date, description, debit_amount FROM banking_transactions WHERE transaction_id = 33094")
bt = cur.fetchone()
print(f"\nBanking Transaction:")
print(f"  Date: {bt[0]}")
print(f"  Description: {bt[1]}")
print(f"  Debit: ${bt[2]}")

# Check overall split usage
print("\n" + "="*70)
print("SPLIT RECEIPT USAGE IN DATABASE")
print("="*70)

cur.execute("SELECT COUNT(*) FROM receipts WHERE is_split_receipt = TRUE AND exclude_from_reports = FALSE")
split_count = cur.fetchone()[0]

cur.execute("SELECT COUNT(*) FROM receipts WHERE split_key IS NOT NULL AND exclude_from_reports = FALSE")
split_key_count = cur.fetchone()[0]

cur.execute("""
    SELECT COUNT(DISTINCT banking_transaction_id) 
    FROM receipts 
    WHERE banking_transaction_id IS NOT NULL 
      AND exclude_from_reports = FALSE
    GROUP BY banking_transaction_id 
    HAVING COUNT(*) > 1
""")
multi_receipt_count = cur.rowcount

print(f"\nReceipts with is_split_receipt=TRUE: {split_count:,}")
print(f"Receipts with split_key: {split_key_count:,}")
print(f"Banking TXs with multiple receipts: {multi_receipt_count:,}")

if split_count == 0 and split_key_count == 0:
    print("\n❌ NO SPLIT FLAGS FOUND - All multi-receipt TXs are likely IMPORT DUPLICATES")
else:
    print(f"\n⚠️  Only {split_count} receipts flagged as splits, but {multi_receipt_count} TXs have multiples")

cur.close()
conn.close()
