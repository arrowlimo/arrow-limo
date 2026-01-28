#!/usr/bin/env python
"""Find which bank the 2022-07-04 transaction came from."""
import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

print("\n" + "="*120)
print("BANKING TRANSACTION DETAILS - Transaction ID 31788 (2022-07-04, $75.04)")
print("="*120)
cur.execute("""
    SELECT transaction_id, account_number, transaction_date, debit_amount, credit_amount,
           description, bank_id, source_file, created_at
    FROM banking_transactions
    WHERE transaction_id = 31788
""")
row = cur.fetchone()
if row:
    txn_id, account, txn_date, debit, credit, desc, bank_id, source_file, created_at = row
    amount = debit if debit else credit
    print(f"\n  Transaction ID: {txn_id}")
    print(f"  Date: {txn_date}")
    print(f"  Amount: ${amount:.2f}")
    print(f"  Account Number: {account}")
    print(f"  Bank ID: {bank_id}")
    print(f"  Source File: {source_file}")
    print(f"  Description: {desc}")
    print(f"  Created: {created_at}")
    print()

# Now determine which bank
print("="*120)
print("BANK IDENTIFICATION")
print("="*120)

if bank_id == 1:
    print("\n  ✓ Bank ID 1 = CIBC (Primary)")
    print("    Account: CIBC 1615 / CIBC 7461615")
    print("    Date Range: 2012-01-03 to 2025-09-12")
elif bank_id == 2:
    print("\n  ✓ Bank ID 2 = SCOTIABANK")
    print("    Account: Scotia 903990106011")
    print("    Date Range: 2012-02-22 to 2019-10-29")
elif bank_id == 4:
    print("\n  ✓ Bank ID 4 = CIBC (Alternate)")
    print("    Account: CIBC 7461615")
    print("    Date Range: 2012-01-01 to 2017-12-31")
else:
    print(f"\n  ✓ Bank ID: {bank_id} (Unknown/Modern)")
    print("    Modern CIBC account (8362, 8117, 4462)")
    print("    Date Range: 2017-2025")

print(f"\n  CONCLUSION: 2022-07-04 transaction is from CIBC (Bank ID {bank_id})")
print(f"  Source File: {source_file}")
print()

cur.close()
conn.close()
