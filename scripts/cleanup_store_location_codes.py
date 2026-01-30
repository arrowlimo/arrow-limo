#!/usr/bin/env python3
"""
Remove store/location codes from specific fast food/retail vendors (explicit list).
Default is dry-run; pass --execute to apply changes.
"""
import psycopg2
import sys

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()

consolidations = {
    "POPEYES #13330": "POPEYES",
    "POPEYES #14011": "POPEYES",
    "MCDONALD'S #159": "MCDONALD'S",
    "MCDONALD'S #406": "MCDONALD'S",
    "MCDONALD'S #703": "MCDONALD'S",
    "MCDONALD'S #718": "MCDONALD'S",
    "MCDONALD'S #400": "MCDONALD'S",
    "A&W #1364": "A&W",
    "BEST BUY #960": "BEST BUY",
    "LOWE'S #3105": "LOWE'S",
    "MICHAELS #3910": "MICHAELS",
    "PIZZA HUT #4781": "PIZZA HUT",
    "TRIPLE O'S #219": "TRIPLE O'S",
    "WHOLESALE CLUB.": "WHOLESALE CLUB",
}

dry_run = '--execute' not in sys.argv

updates = []
for old, new in consolidations.items():
    cur.execute("SELECT COUNT(*) FROM receipts WHERE vendor_name = %s", (old,))
    count = cur.fetchone()[0]
    if count:
        updates.append((old, new, count))

total = sum(c for _, _, c in updates)
print(f"Found {len(updates)} vendor variations affecting {total} receipts\n")
print("CONSOLIDATIONS TO APPLY")
print("=" * 70)
for old, new, count in updates:
    print(f"{count:>5} | {old:<30} → {new}")

if not updates:
    print("\nNothing to do.")
    cur.close(); conn.close(); sys.exit(0)

if dry_run:
    print("\n✅ DRY RUN COMPLETE")
    print("Run with --execute to apply consolidations")
else:
    print("\n⚠️  EXECUTION MODE")
    response = input(f"\nType 'CONSOLIDATE' to update {total} receipts: ")
    if response != 'CONSOLIDATE':
        print("❌ Cancelled")
        cur.close(); conn.close(); sys.exit(0)

    print("\n📝 Consolidating vendor names...")
    for old, new, count in updates:
        cur.execute("UPDATE receipts SET vendor_name = %s WHERE vendor_name = %s", (new, old))
    conn.commit()
    print(f"   ✅ Updated {total} receipts")
    print("\n✅ CONSOLIDATION COMPLETE")

cur.close(); conn.close()
