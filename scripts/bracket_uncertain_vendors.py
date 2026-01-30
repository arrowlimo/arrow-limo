#!/usr/bin/env python3
"""
Add brackets to uncertain vendor names extracted from POINT OF SALE receipts
"""
import psycopg2
import sys

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()

# Mapping of extracted vendor names to bracketed versions
vendor_mappings = {
    'FAS': '[FAS GAS]',
    'KAL': '[KAL TIRE]',
    'THE': '[THE BRICK]',
    'WAL': '[WALMART]',
    'TIM': '[TIM HORTONS]',
    'BED': '[BED BATH & BEYOND]',
    'REAL': '[REAL CANADIAN SUPERSTORE]',
    'REAL CON.': '[REAL CANADIAN SUPERSTORE]',
    'TONY': '[TONY ROMAS]',
    'WOK': '[WOK BOX]',
    'OLD': '[OLD SPAGHETTI FACTORY]',
    'RED': '[RED LOBSTER]',
    'EAST': '[EAST SIDE MARIOS]',
    'ALL': '[ALLSTATE]',
    'LIQUOR DEPOT': 'LIQUOR BARN',  # 604 code = known LIQUOR BARN, 601 was wrongly called DEPOT
    'STORE 600': '[STORE 600]',
    'STORE 606': '[STORE 606]',
}

dry_run = '--dry-run' in sys.argv or len(sys.argv) == 1

# Find receipts with these vendor names
updates = []
for old_vendor, new_vendor in vendor_mappings.items():
    cur.execute("""
        SELECT receipt_id, vendor_name
        FROM receipts
        WHERE vendor_name = %s
    """, (old_vendor,))
    
    for receipt_id, vendor_name in cur.fetchall():
        updates.append((receipt_id, vendor_name, new_vendor))

print(f"Found {len(updates)} receipts with uncertain vendor names to mark\n")

# Show summary
from collections import Counter
summary = Counter(new_vendor for _, _, new_vendor in updates)
print("VENDOR UPDATES")
print("=" * 60)
for vendor, count in sorted(summary.items()):
    print(f"{count:>5} | {vendor}")

if dry_run:
    print("\n✅ DRY RUN COMPLETE")
    print("Run with --execute to add brackets to uncertain vendors")
else:
    print("\n⚠️  EXECUTION MODE")
    response = input(f"\nType 'BRACKET' to update {len(updates)} vendor names: ")
    
    if response != 'BRACKET':
        print("❌ Cancelled")
        cur.close()
        conn.close()
        sys.exit(0)
    
    print("\n📝 Adding brackets to uncertain vendor names...")
    for receipt_id, old_vendor, new_vendor in updates:
        cur.execute("""
            UPDATE receipts
            SET vendor_name = %s
            WHERE receipt_id = %s
        """, (new_vendor, receipt_id))
    
    conn.commit()
    print(f"   ✅ Updated {len(updates)} vendor names with brackets")
    print("\n✅ BRACKETING COMPLETE")

cur.close()
conn.close()
