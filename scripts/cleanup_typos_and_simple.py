#!/usr/bin/env python3
"""
Clean up obvious typos and simple consolidations
"""
import psycopg2
import sys

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()

# Simple consolidations (typos and clear variations)
consolidations = {
    'SOBEY\'S': 'SOBEYS',
    'CANADAINA TIRE': 'CANADIAN TIRE',
    # RED DEER SUPERV SERVICES stays separate (not RCSS)
    'MONEYMART': 'MONEY MART',
    'ERIES AUTO REPAIR': 'ERLES AUTO REPAIR',
    'ERLES AUTO REPA': 'ERLES AUTO REPAIR',
    'SAVE ON FOODA': 'SAVE ON FOODS',
    'E-TRANSFER ?': 'TRANSFER',
    'MERCHANT SERVICES FEE': 'BANK SERVICE FEE',
}

dry_run = '--dry-run' in sys.argv or len(sys.argv) == 1

# Find receipts with these vendor names
updates = []
for old_vendor, new_vendor in consolidations.items():
    cur.execute("""
        SELECT COUNT(*) FROM receipts WHERE vendor_name = %s
    """, (old_vendor,))
    count = cur.fetchone()[0]
    if count > 0:
        updates.append((old_vendor, new_vendor, count))

total_receipts = sum(cnt for _, _, cnt in updates)

print(f"Found {len(updates)} vendor variations affecting {total_receipts} receipts\n")
print("CONSOLIDATIONS TO APPLY")
print("=" * 70)
for old_vendor, new_vendor, count in updates:
    print(f"{count:>5} | {old_vendor:<30} → {new_vendor}")

if dry_run:
    print("\n✅ DRY RUN COMPLETE")
    print("Run with --execute to apply consolidations")
else:
    print("\n⚠️  EXECUTION MODE")
    response = input(f"\nType 'CONSOLIDATE' to update {total_receipts} receipts: ")
    
    if response != 'CONSOLIDATE':
        print("❌ Cancelled")
        cur.close()
        conn.close()
        sys.exit(0)
    
    print("\n📝 Consolidating vendor names...")
    for old_vendor, new_vendor, count in updates:
        cur.execute("""
            UPDATE receipts
            SET vendor_name = %s
            WHERE vendor_name = %s
        """, (new_vendor, old_vendor))
    
    conn.commit()
    print(f"   ✅ Updated {total_receipts} receipts")
    print("\n✅ CONSOLIDATION COMPLETE")

cur.close()
conn.close()
