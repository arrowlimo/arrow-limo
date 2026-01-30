#!/usr/bin/env python3
"""Delete duplicate receipts - keep the first one (lower ID), delete the rest."""

import psycopg2

# Dry run mode
DRY_RUN = False

conn = psycopg2.connect(
    host="localhost",
    database="almsdata",
    user="postgres",
    password="***REDACTED***"
)

cur = conn.cursor()

print("=" * 100)
print("DELETE DUPLICATE RECEIPTS")
print("=" * 100)
print(f"\nMode: {'DRY RUN (no changes)' if DRY_RUN else 'LIVE (will delete)'}")
print("=" * 100)

# Find all duplicate groups
cur.execute("""
    WITH grouped AS (
        SELECT 
            receipt_date,
            gross_amount,
            COALESCE(canonical_vendor, vendor_name) as vendor,
            ARRAY_AGG(receipt_id ORDER BY receipt_id) as receipt_ids,
            COUNT(*) as count
        FROM receipts
        WHERE exclude_from_reports = false OR exclude_from_reports IS NULL
        GROUP BY receipt_date, gross_amount, vendor
        HAVING COUNT(*) > 1
          AND (COUNT(DISTINCT banking_transaction_id) FILTER (WHERE banking_transaction_id IS NOT NULL) <= 1)
    )
    SELECT 
        receipt_date,
        gross_amount,
        vendor,
        receipt_ids,
        count
    FROM grouped
    ORDER BY receipt_date
""")

duplicate_groups = cur.fetchall()

# Extract IDs to delete (all except the first one in each group)
ids_to_delete = []
for date, amount, vendor, receipt_ids, count in duplicate_groups:
    # Keep first ID, delete the rest
    for rid in receipt_ids[1:]:
        ids_to_delete.append((rid, date, amount, vendor))

print(f"\nFound {len(duplicate_groups)} duplicate groups")
print(f"Total receipts to delete: {len(ids_to_delete)} (keeping {len(duplicate_groups)} - one per group)")

# Show sample
print("\n" + "=" * 100)
print("SAMPLE RECEIPTS TO DELETE (first 20)")
print("=" * 100)
print(f"\n{'Receipt ID':<12s} | {'Date':<12s} | {'Amount':>10s} | {'Vendor':<40s}")
print("-" * 90)

for rid, date, amount, vendor in ids_to_delete[:20]:
    vendor_display = str(vendor)[:40] if vendor else "Unknown"
    amt_display = f"${float(amount):.2f}" if amount else "None"
    print(f"{rid:<12d} | {str(date):<12s} | {amt_display:>10s} | {vendor_display}")

if DRY_RUN:
    print("\n" + "=" * 100)
    print("DRY RUN COMPLETE - No receipts deleted")
    print("=" * 100)
    print(f"\nTo delete these {len(ids_to_delete)} duplicate receipts, edit this script:")
    print("  Change: DRY_RUN = False")
    print("  Then run again")
else:
    print("\n" + "=" * 100)
    print("DELETING DUPLICATES...")
    print("=" * 100)
    
    deleted_count = 0
    for rid, date, amount, vendor in ids_to_delete:
        # First, update any banking_transactions that reference this receipt to NULL
        cur.execute("UPDATE banking_transactions SET receipt_id = NULL WHERE receipt_id = %s", (rid,))
        
        # Now delete the receipt
        cur.execute("DELETE FROM receipts WHERE receipt_id = %s", (rid,))
        deleted_count += 1
        if deleted_count % 100 == 0:
            print(f"  ✓ Deleted {deleted_count:,} receipts...")
    
    conn.commit()
    print(f"\n✅ Successfully deleted {deleted_count:,} duplicate receipts")
    print(f"   Kept {len(duplicate_groups):,} receipts (one per group)")
    print("=" * 100)

cur.close()
conn.close()
