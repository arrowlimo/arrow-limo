#!/usr/bin/env python3
"""
Revert and bracket uncertain deposits for later investigation after deduplication
"""
import psycopg2
import sys

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()

# Revert to original names with brackets to mark as uncertain
revert_mappings = {
    'IFS NSF REFUND': '[DEPOSIT FROM IFS]',  # Uncertain - investigate after dedup
    'INSURANCE/POLICY REFUND': '[DEPOSIT FROM CAMBRIDGE ON]',  # Uncertain - investigate after dedup
}

dry_run = '--dry-run' in sys.argv or len(sys.argv) == 1

# Find receipts with these vendor names
updates = []
for old_vendor, new_vendor in revert_mappings.items():
    cur.execute("""
        SELECT receipt_id, vendor_name
        FROM receipts
        WHERE vendor_name = %s
    """, (old_vendor,))
    
    for receipt_id, vendor_name in cur.fetchall():
        updates.append((receipt_id, vendor_name, new_vendor))

print(f"Found {len(updates)} receipts to revert and bracket\n")

# Show summary
from collections import Counter
summary = Counter(new_vendor for _, _, new_vendor in updates)
print("REVERT AND BRACKET SUMMARY")
print("=" * 70)
for vendor, count in sorted(summary.items()):
    print(f"{count:>5} | {vendor}")

if dry_run:
    print("\n✅ DRY RUN COMPLETE")
    print("Run with --execute to revert and bracket uncertain deposits")
else:
    print("\n⚠️  EXECUTION MODE")
    response = input(f"\nType 'REVERT' to update {len(updates)} vendor names: ")
    
    if response != 'REVERT':
        print("❌ Cancelled")
        cur.close()
        conn.close()
        sys.exit(0)
    
    print("\n📝 Reverting and bracketing uncertain deposits...")
    for receipt_id, old_vendor, new_vendor in updates:
        cur.execute("""
            UPDATE receipts
            SET vendor_name = %s
            WHERE receipt_id = %s
        """, (new_vendor, receipt_id))
    
    conn.commit()
    print(f"   ✅ Updated {len(updates)} vendor names")
    print("\n✅ REVERT COMPLETE")
    print("\nNote: Bracketed deposits will be investigated after deduplication")
    print("(may disappear if they're duplicates of WITHDRAWAL entries)")

cur.close()
conn.close()
