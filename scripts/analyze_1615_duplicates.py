#!/usr/bin/env python3
"""
Analyze and fix account 1615 -> Move to proper CIBC account (0228362)
"""

import psycopg2
import hashlib

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

print("="*80)
print("ANALYZING ACCOUNT 1615 TRANSACTIONS")
print("="*80)

# Get all 1615 transactions
cur.execute("""
    SELECT transaction_id, transaction_date, description, 
           debit_amount, credit_amount, balance, source_file
    FROM banking_transactions
    WHERE account_number = '1615'
    ORDER BY transaction_date
""")

trans_1615 = cur.fetchall()
print(f"\nAccount 1615: {len(trans_1615)} transactions")

# Create signatures to check for duplicates
signatures_1615 = {}
for t in trans_1615:
    sig = f"{t[1]}|{t[2]}|{float(t[3] or 0):.2f}|{float(t[4] or 0):.2f}"
    signatures_1615[sig] = t[0]  # transaction_id

print(f"Unique signatures in 1615: {len(signatures_1615)}")

# Check if these exist in 0228362
print("\n" + "="*80)
print("CHECKING FOR DUPLICATES IN ACCOUNT 0228362")
print("="*80)

duplicates = []
unique_to_1615 = []

for sig, txn_id in signatures_1615.items():
    parts = sig.split('|')
    date = parts[0]
    desc = parts[1]
    debit = float(parts[2])
    credit = float(parts[3])
    
    # Check if this transaction exists in 0228362
    cur.execute("""
        SELECT transaction_id
        FROM banking_transactions
        WHERE account_number = '0228362'
          AND transaction_date = %s
          AND description = %s
          AND COALESCE(debit_amount, 0) = %s
          AND COALESCE(credit_amount, 0) = %s
    """, (date, desc, debit if debit > 0 else None, credit if credit > 0 else None))
    
    existing = cur.fetchone()
    if existing:
        duplicates.append((txn_id, existing[0]))
    else:
        unique_to_1615.append(txn_id)

print(f"\n✅ Duplicates (already in 0228362): {len(duplicates)}")
print(f"🆕 Unique to 1615 (need to move): {len(unique_to_1615)}")

# Show sample of each
if duplicates:
    print("\nSample duplicates (first 5):")
    for i, (id_1615, id_0228362) in enumerate(duplicates[:5]):
        cur.execute("SELECT transaction_date, description FROM banking_transactions WHERE transaction_id = %s", (id_1615,))
        t = cur.fetchone()
        print(f"  {t[0]} | {t[1][:50]}")

if unique_to_1615:
    print("\nSample unique transactions (first 10):")
    for txn_id in unique_to_1615[:10]:
        cur.execute("SELECT transaction_date, description, debit_amount, credit_amount FROM banking_transactions WHERE transaction_id = %s", (txn_id,))
        t = cur.fetchone()
        debit = f"${t[2]:,.2f}" if t[2] else ""
        credit = f"${t[3]:,.2f}" if t[3] else ""
        print(f"  {t[0]} | {t[1][:40]:<40} | D:{debit:>12} C:{credit:>12}")

# Check date ranges
print("\n" + "="*80)
print("DATE RANGE ANALYSIS")
print("="*80)

cur.execute("""
    SELECT MIN(transaction_date), MAX(transaction_date)
    FROM banking_transactions
    WHERE account_number = '1615'
""")
min_1615, max_1615 = cur.fetchone()

cur.execute("""
    SELECT MIN(transaction_date), MAX(transaction_date)
    FROM banking_transactions
    WHERE account_number = '0228362'
""")
min_0228362, max_0228362 = cur.fetchone()

print(f"\nAccount 1615: {min_1615} to {max_1615}")
print(f"Account 0228362: {min_0228362} to {max_0228362}")

# Recommendation
print("\n" + "="*80)
print("RECOMMENDATION")
print("="*80)

if len(duplicates) == len(trans_1615):
    print("\n✅ ALL transactions in 1615 are duplicates of 0228362")
    print("   Safe to DELETE account 1615 transactions")
    print("\nAction: DELETE FROM banking_transactions WHERE account_number = '1615'")
elif len(unique_to_1615) > 0:
    print(f"\n⚠️  {len(unique_to_1615)} transactions in 1615 are NOT in 0228362")
    print("   Need to UPDATE these to account 0228362")
    print(f"   DELETE {len(duplicates)} duplicates")
    print("\nAction:")
    print(f"  1. UPDATE {len(unique_to_1615)} unique transactions: account_number = '0228362'")
    print(f"  2. DELETE {len(duplicates)} duplicate transactions")

print("\nType 'yes' to proceed with the fix:")

cur.close()
conn.close()
