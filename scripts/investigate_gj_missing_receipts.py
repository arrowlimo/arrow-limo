#!/usr/bin/env python3
"""
Investigate why 6 of 7 General Journal banking transactions 
didn't create receipts.

Created: November 25, 2025
"""

import psycopg2
import os

conn = psycopg2.connect(
    host=os.getenv('DB_HOST', 'localhost'),
    database=os.getenv('DB_NAME', 'almsdata'),
    user=os.getenv('DB_USER', 'postgres'),
    password=os.getenv('DB_PASSWORD', '***REMOVED***')
)
cur = conn.cursor()

print("\nINVESTIGATING MISSING GENERAL JOURNAL RECEIPTS")
print("="*80)

# Find all General Journal banking transactions
cur.execute("""
    SELECT 
        transaction_id,
        transaction_date,
        description,
        debit_amount,
        credit_amount,
        account_number
    FROM banking_transactions
    WHERE account_number = '903990106011'
    AND (
        description ILIKE '%general journal%' 
        OR description ILIKE '%gen j%'
        OR description ILIKE 'gj %'
    )
    ORDER BY transaction_date
""")

gj_banking = cur.fetchall()
print(f"\n1. General Journal banking transactions: {len(gj_banking)}")
for row in gj_banking:
    tid, date, desc, debit, credit, acct = row
    amt = debit if debit else credit
    direction = "DR" if debit else "CR"
    print(f"   [{tid:5}] {date} ${amt:>10.2f} {direction} {desc[:50]}")

# Check if they're linked to receipts
print(f"\n2. Checking receipt linkage...")
for row in gj_banking:
    tid = row[0]
    date = row[1]
    desc = row[2]
    debit = row[3]
    credit = row[4]
    
    # Check if linked in junction table
    cur.execute("""
        SELECT 
            bm.receipt_id,
            r.gross_amount,
            r.category
        FROM banking_receipt_matching_ledger bm
        JOIN receipts r ON r.receipt_id = bm.receipt_id
        WHERE bm.banking_transaction_id = %s
    """, (tid,))
    
    link = cur.fetchone()
    
    if link:
        rid, amt, cat = link
        print(f"   ✓ [{tid:5}] LINKED to receipt {rid} (${amt:.2f}, {cat})")
    else:
        amt = debit if debit else credit
        direction = "DEBIT" if debit else "CREDIT"
        print(f"   ✗ [{tid:5}] NOT LINKED - ${amt:.2f} {direction}")
        
        # Was this a credit (money IN)?
        if credit and credit > 0:
            print(f"      → Reason: Credits (deposits) are ignored by auto-create script")
            print(f"      → Script only processes DEBITS (expenses)")
        elif debit and debit > 0:
            print(f"      → Reason: UNKNOWN - this is a debit, should have created receipt")

print(f"\n3. Summary:")
cur.execute("""
    SELECT COUNT(DISTINCT bt.transaction_id)
    FROM banking_transactions bt
    WHERE account_number = '903990106011'
    AND (
        description ILIKE '%general journal%' 
        OR description ILIKE '%gen j%'
        OR description ILIKE 'gj %'
    )
    AND EXISTS (
        SELECT 1 FROM banking_receipt_matching_ledger bm
        WHERE bm.banking_transaction_id = bt.transaction_id
    )
""")
linked = cur.fetchone()[0]

print(f"   Total GJ banking transactions: {len(gj_banking)}")
print(f"   Linked to receipts: {linked}")
print(f"   Not linked: {len(gj_banking) - linked}")

print("\n" + "="*80)
print("EXPLANATION:")
print("="*80)
print("\n1. The auto_create_receipts_from_all_banking.py script ONLY processes:")
print("   - Banking transactions with debit_amount > 0 (expenses)")
print("   - Ignores credit_amount transactions (deposits/income)")
print("")
print("2. General Journal entries can be:")
print("   - Debits (expenses/adjustments) → should create receipts")
print("   - Credits (income/adjustments) → ignored by script")
print("")
print("3. If debits are not linked, they should be processed manually")

cur.close()
conn.close()
