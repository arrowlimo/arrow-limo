#!/usr/bin/env python3
"""
Query banking_transactions table to verify which Oct 1, 2012 transactions 
are from real bank statements vs QuickBooks.
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
print("VERIFY OCT 1, 2012 IN BANKING_TRANSACTIONS (ACTUAL BANK DATA)")
print("=" * 80)

# Get all Oct 1, 2012 transactions
cur.execute("""
    SELECT transaction_id, 
           CASE WHEN bank_id = 1 THEN 'CIBC' WHEN bank_id = 2 THEN 'SCOTIA' ELSE 'Unknown' END as bank,
           CASE WHEN debit_amount IS NOT NULL THEN 'DEBIT' ELSE 'CREDIT' END as type,
           COALESCE(debit_amount, credit_amount) as amount,
           description,
           reconciliation_status
    FROM banking_transactions
    WHERE transaction_date = '2012-10-01'
    ORDER BY bank_id, transaction_id
""")

transactions = cur.fetchall()
print(f"\nTotal transactions in banking_transactions: {len(transactions)}\n")

cibc_list = []
scotia_list = []
unknown_list = []

for tx_id, bank, tx_type, amount, desc, status in transactions:
    row = (tx_id, bank, tx_type, amount, desc, status)
    if bank == 'CIBC':
        cibc_list.append(row)
    elif bank == 'SCOTIA':
        scotia_list.append(row)
    else:
        unknown_list.append(row)

# Report CIBC
print("=" * 80)
print(f"CIBC TRANSACTIONS ({len(cibc_list)}):")
print("=" * 80)
for tx_id, bank, tx_type, amount, desc, status in cibc_list:
    status_display = f"[{status}]" if status else ""
    print(f"TX {tx_id:6d} | {tx_type:6} | ${amount:>10,.2f} | {desc[:50]} {status_display}")

# Report Scotia
print("\n" + "=" * 80)
print(f"SCOTIA TRANSACTIONS ({len(scotia_list)}):")
print("=" * 80)
for tx_id, bank, tx_type, amount, desc, status in scotia_list:
    status_display = f"[{status}]" if status else ""
    print(f"TX {tx_id:6d} | {tx_type:6} | ${amount:>10,.2f} | {desc[:50]} {status_display}")

# Report Unknown
print("\n" + "=" * 80)
print(f"UNKNOWN BANK (QuickBooks imports) ({len(unknown_list)}):")
print("=" * 80)
for tx_id, bank, tx_type, amount, desc, status in unknown_list:
    status_display = f"[{status}]" if status else ""
    print(f"TX {tx_id:6d} | {tx_type:6} | ${amount:>10,.2f} | {desc[:50]} {status_display}")

# Analysis
print("\n" + "=" * 80)
print("ANALYSIS:")
print("=" * 80)

print(f"\nCIBC ({len(cibc_list)} transactions):")
print("  - These ARE in banking_transactions table (real bank data)")
print("  - CIBC has 3 mixed accounts (not fully verified)")
print("  - Might be legitimate unmatched transactions")

print(f"\nScotia ({len(scotia_list)} transactions):")
print("  - These ARE in banking_transactions table")
print("  - You said Scotia is FULLY MATCHED")
print("  - If they have no receipts, need investigation")
print("  - Either: 1) Real transactions needing receipts, OR")
print("  -         2) Duplicates/QB entries wrongly in Scotia bank_id")

print(f"\nUnknown ({len(unknown_list)} transactions):")
print("  - These are QuickBooks imports (bank_id = NULL/Unknown)")
print("  - NOT from bank statements")
print("  - Should be marked as QB entries")

# Check for receipts
print("\n" + "=" * 80)
print("RECEIPT STATUS:")
print("=" * 80)

all_tx_ids = [t[0] for t in cibc_list + scotia_list]

cur.execute("""
    SELECT banking_transaction_id, COUNT(*)
    FROM receipts
    WHERE banking_transaction_id = ANY(%s)
    GROUP BY banking_transaction_id
""", (all_tx_ids,))

receipts_map = {tx_id: count for tx_id, count in cur.fetchall()}

cibc_with_receipts = sum(1 for t in cibc_list if t[0] in receipts_map)
scotia_with_receipts = sum(1 for t in scotia_list if t[0] in receipts_map)

print(f"CIBC: {cibc_with_receipts}/{len(cibc_list)} have receipts")
print(f"Scotia: {scotia_with_receipts}/{len(scotia_list)} have receipts")

print("\n" + "=" * 80)
print("CONCLUSION:")
print("=" * 80)
print(f"These {len(cibc_list)} CIBC + {len(scotia_list)} Scotia transactions ARE in the banking_transactions table.")
print("They were imported from actual bank statements, NOT QuickBooks.")
print("If you said Scotia is fully matched, these Scotia transactions should have receipts.")
print("They need investigation - either create receipts OR mark as duplicates if already processed.")

cur.close()
conn.close()
