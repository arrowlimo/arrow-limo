#!/usr/bin/env python3
"""Investigate receipts created from banking but now orphaned."""

import psycopg2
import os

conn = psycopg2.connect(
    host=os.environ.get("DB_HOST", "localhost"),
    database=os.environ.get("DB_NAME", "almsdata"),
    user=os.environ.get("DB_USER", "postgres"),
    password=os.environ.get("DB_PASSWORD", "***REDACTED***")
)
cur = conn.cursor()

print("=" * 100)
print("INVESTIGATING: Receipts Created From Banking But Now Orphaned")
print("=" * 100)

# Check if these receipts still reference a banking_transaction_id in the ledger
print("\n1. Checking if banking links exist in matching ledger:")
cur.execute("""
    SELECT r.receipt_id, r.vendor_name, r.gross_amount, r.receipt_date,
           bml.banking_transaction_id
    FROM receipts r
    LEFT JOIN banking_receipt_matching_ledger bml ON bml.receipt_id = r.receipt_id
    WHERE EXTRACT(YEAR FROM r.receipt_date) BETWEEN 2020 AND 2025
    AND r.banking_transaction_id IS NULL
    AND r.created_from_banking = true
    LIMIT 20
""")
ledger_check = cur.fetchall()
print(f"Sample of {len(ledger_check)} orphaned receipts:")
for rid, vendor, amount, rdate, banking_tx_id in ledger_check:
    amt_str = f"${amount:,.2f}" if amount else "NULL"
    ledger_status = "HAS LEDGER LINK" if banking_tx_id else "NO LEDGER LINK"
    print(f"  {rid:7} | {rdate} | {vendor[:40]:40} | {amt_str:>12} | {ledger_status}")

# Check if the banking_transaction_id column is just NULL but the link exists elsewhere
print("\n2. CRITICAL: Why are banking_transaction_id values NULL?")
cur.execute("""
    SELECT COUNT(*) as count
    FROM receipts r
    WHERE EXTRACT(YEAR FROM r.receipt_date) BETWEEN 2020 AND 2025
    AND r.banking_transaction_id IS NULL
    AND r.created_from_banking = true
    AND EXISTS (
        SELECT 1 FROM banking_receipt_matching_ledger bml 
        WHERE bml.receipt_id = r.receipt_id
    )
""")
has_ledger_link = cur.fetchone()[0]
print(f"  Receipts with NULL banking_transaction_id BUT ledger link exists: {has_ledger_link}")

# If ledger links exist, we should restore them
if has_ledger_link > 0:
    print(f"\n⚠️  ISSUE FOUND: {has_ledger_link} receipts have ledger links but NULL banking_transaction_id")
    print("  This suggests the banking_transaction_id column was cleared/reset")
    print("  RECOMMENDATION: Restore banking_transaction_id from ledger")
    
    # Show what can be restored
    print("\n3. RESTORATION PREVIEW:")
    cur.execute("""
        SELECT r.receipt_id, r.vendor_name, r.gross_amount,
               bml.banking_transaction_id, bt.description
        FROM receipts r
        JOIN banking_receipt_matching_ledger bml ON bml.receipt_id = r.receipt_id
        JOIN banking_transactions bt ON bt.transaction_id = bml.banking_transaction_id
        WHERE EXTRACT(YEAR FROM r.receipt_date) BETWEEN 2020 AND 2025
        AND r.banking_transaction_id IS NULL
        AND r.created_from_banking = true
        LIMIT 15
    """)
    restorable = cur.fetchall()
    for rid, vendor, amount, banking_tx_id, banking_desc in restorable:
        amt_str = f"${amount:,.2f}" if amount else "NULL"
        print(f"  Receipt {rid}: {vendor[:30]:30} | {amt_str:>12} → Banking TX {banking_tx_id}")
        print(f"    Banking: {banking_desc[:70]}")

# Check for Heffner specifically since it's the biggest
print("\n4. HEFFNER ORPHAN BREAKDOWN:")
cur.execute("""
    SELECT 
        EXTRACT(YEAR FROM receipt_date) as year,
        COUNT(*) as orphan_count,
        SUM(gross_amount) as orphan_amount
    FROM receipts
    WHERE vendor_name LIKE '%HEFFNER%'
    AND EXTRACT(YEAR FROM receipt_date) BETWEEN 2020 AND 2025
    AND banking_transaction_id IS NULL
    GROUP BY EXTRACT(YEAR FROM receipt_date)
    ORDER BY year
""")
heffner_orphans = cur.fetchall()
for year, count, amount in heffner_orphans:
    amt_str = f"${amount:,.2f}" if amount else "$0.00"
    print(f"  {int(year)}: {count:4} orphans, {amt_str:>12}")

# Check if Heffner entries have ledger links
cur.execute("""
    SELECT COUNT(*)
    FROM receipts r
    WHERE r.vendor_name LIKE '%HEFFNER%'
    AND EXTRACT(YEAR FROM r.receipt_date) BETWEEN 2020 AND 2025
    AND r.banking_transaction_id IS NULL
    AND EXISTS (
        SELECT 1 FROM banking_receipt_matching_ledger bml 
        WHERE bml.receipt_id = r.receipt_id
    )
""")
heffner_restorable = cur.fetchone()[0]
print(f"\n  Heffner receipts restorable from ledger: {heffner_restorable}")

# Summary
print("\n" + "=" * 100)
print("DIAGNOSIS")
print("=" * 100)
print(f"""
The receipts were created_from_banking=true but now have NULL banking_transaction_id.

This happened because:
  1. Receipts were created from banking imports (created_from_banking=true)
  2. The banking_transaction_id column was later cleared/reset
  3. The ledger table still has the links

SOLUTION:
  Restore banking_transaction_id from banking_receipt_matching_ledger table
  This will convert {has_ledger_link:,} "orphans" back to linked receipts
""")

cur.close()
conn.close()
