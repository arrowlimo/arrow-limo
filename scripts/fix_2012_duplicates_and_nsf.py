#!/usr/bin/env python3
"""Fix 2012 duplicate receipts and incorrect NSF transaction signs."""

import psycopg2
import os
from datetime import datetime
import openpyxl

# Database connection
conn = psycopg2.connect(
    host=os.getenv('DB_HOST', 'localhost'),
    user=os.getenv('DB_USER', 'postgres'),
    password=os.getenv('DB_PASSWORD', '***REDACTED***'),
    database=os.getenv('DB_NAME', 'almsdata')
)
cur = conn.cursor()

print("="*70)
print("FIXING 2012 RECEIPT DUPLICATES AND NSF TRANSACTIONS")
print("="*70)
print()

# STEP 1: Find and remove duplicate receipts for 2012
print("STEP 1: Finding duplicate receipts (2012)...")
print()

cur.execute("""
    SELECT 
        receipt_date,
        vendor_name,
        gross_amount,
        COUNT(*) as dup_count,
        array_agg(receipt_id ORDER BY receipt_id) as receipt_ids
    FROM receipts
    WHERE EXTRACT(YEAR FROM receipt_date) = 2012
    GROUP BY receipt_date, vendor_name, gross_amount
    HAVING COUNT(*) > 1
    ORDER BY COUNT(*) DESC, gross_amount DESC
""")

duplicates = cur.fetchall()
print(f"Found {len(duplicates)} duplicate groups")
print()

total_to_delete = 0
for date, vendor, amount, dup_count, receipt_ids in duplicates[:10]:
    print(f"  {date} | {vendor[:30]:30} | ${amount:10,.2f} | {dup_count} copies | IDs: {receipt_ids}")
    total_to_delete += (dup_count - 1)  # Keep first, delete rest

print()
print(f"Total duplicate receipts to delete: {total_to_delete}")
print()

# Create backup before deletion
timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
backup_table = f'receipts_2012_duplicates_backup_{timestamp}'

print(f"Creating backup: {backup_table}")
cur.execute(f"""
    CREATE TABLE {backup_table} AS
    SELECT r.*
    FROM receipts r
    WHERE r.receipt_id IN (
        SELECT unnest(receipt_ids[2:]) 
        FROM (
            SELECT array_agg(receipt_id ORDER BY receipt_id) as receipt_ids
            FROM receipts
            WHERE EXTRACT(YEAR FROM receipt_date) = 2012
            GROUP BY receipt_date, vendor_name, gross_amount
            HAVING COUNT(*) > 1
        ) dups
    )
""")
conn.commit()
print(f"Backed up {cur.rowcount} duplicate receipts")
print()

# Delete duplicates (keep first occurrence)
print("Deleting duplicate receipts (keeping first occurrence)...")
cur.execute("""
    DELETE FROM receipts
    WHERE receipt_id IN (
        SELECT unnest(receipt_ids[2:]) 
        FROM (
            SELECT array_agg(receipt_id ORDER BY receipt_id) as receipt_ids
            FROM receipts
            WHERE EXTRACT(YEAR FROM receipt_date) = 2012
            GROUP BY receipt_date, vendor_name, gross_amount
            HAVING COUNT(*) > 1
        ) dups
    )
""")
deleted_count = cur.rowcount
conn.commit()
print(f"✅ Deleted {deleted_count} duplicate receipts")
print()

# STEP 2: Fix NSF transaction signs in banking_transactions
print("STEP 2: Fixing NSF transaction signs in banking_transactions...")
print()

# Find NSF charges (should be withdrawals/debits)
cur.execute("""
    SELECT transaction_id, transaction_date, description, debit_amount, credit_amount
    FROM banking_transactions
    WHERE EXTRACT(YEAR FROM transaction_date) = 2012
    AND (description ILIKE '%NSF%' OR description ILIKE '%bounce%' OR description ILIKE '%non-sufficient%')
    ORDER BY transaction_date
""")

nsf_transactions = cur.fetchall()
print(f"Found {len(nsf_transactions)} NSF-related transactions in 2012")
print()

corrections_needed = 0
for txn_id, date, desc, debit, credit in nsf_transactions:
    # NSF CHARGE should be debit (money out)
    # NSF REVERSAL/CORRECTION should be credit (money back)
    
    if 'CHARGE' in desc.upper():
        if credit and not debit:
            print(f"  ⚠️ NSF CHARGE as credit: {date} | {desc[:50]} | ${credit:,.2f}")
            corrections_needed += 1
            # Should be: move credit to debit
            cur.execute("""
                UPDATE banking_transactions
                SET debit_amount = credit_amount, credit_amount = NULL
                WHERE transaction_id = %s
            """, (txn_id,))
    
    elif 'CORRECTION' in desc.upper() or 'REVERSAL' in desc.upper():
        if debit and not credit:
            print(f"  ⚠️ NSF REVERSAL as debit: {date} | {desc[:50]} | ${debit:,.2f}")
            corrections_needed += 1
            # Should be: move debit to credit
            cur.execute("""
                UPDATE banking_transactions
                SET credit_amount = debit_amount, debit_amount = NULL
                WHERE transaction_id = %s
            """, (txn_id,))

if corrections_needed > 0:
    conn.commit()
    print()
    print(f"✅ Fixed {corrections_needed} NSF transaction signs")
else:
    print("✅ No NSF transaction corrections needed")

print()

# STEP 3: Regenerate receipts for any unlinked banking transactions
print("STEP 3: Checking for unlinked banking debits...")
cur.execute("""
    SELECT COUNT(*)
    FROM banking_transactions bt
    WHERE EXTRACT(YEAR FROM bt.transaction_date) = 2012
    AND bt.debit_amount > 0
    AND NOT EXISTS (
        SELECT 1 FROM banking_receipt_matching_ledger bm
        WHERE bm.banking_transaction_id = bt.transaction_id
    )
""")

unlinked = cur.fetchone()[0]
print(f"Found {unlinked} unlinked banking debits in 2012")

if unlinked > 0:
    print("Run auto_create_receipts_from_all_banking.py to create receipts for these")

print()
print("="*70)
print("SUMMARY")
print("="*70)
print(f"  ✅ Deleted {deleted_count} duplicate receipts")
print(f"  ✅ Fixed {corrections_needed} NSF transaction signs")
print(f"  ℹ️  {unlinked} banking transactions need receipt creation")
print()
print("NEXT STEPS:")
print("  1. Run reconcile_2012_banking_receipts_to_excel.py to regenerate clean Excel")
print("  2. Review NSF transactions to confirm they now cancel out correctly")
print("="*70)

conn.close()
