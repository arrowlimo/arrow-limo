#!/usr/bin/env python3
"""
Convert remaining POINTOFSALE receipts with no vendor name to [UNKNOWN POINT OF SALE]
"""
import psycopg2
import re
import sys

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()

# Get all remaining POINTOFSALE receipts that still have no vendor name,
# but skip international Visa debit descriptors (INTL*), since those
# indicate US transactions and should be handled separately.
cur.execute("""
        SELECT receipt_id, vendor_name
        FROM receipts
        WHERE (vendor_name ILIKE '%point%of%sale%' OR vendor_name ILIKE '%pointofsale%')
            AND vendor_name NOT ILIKE '%intl%'
            AND vendor_name NOT IN (
                SELECT DISTINCT vendor_name FROM receipts 
                WHERE vendor_name ILIKE '%point%of%sale%' 
                    AND (
                        vendor_name ILIKE '%[%' OR 
                        vendor_name ILIKE '%liquor%' OR
                        vendor_name ILIKE '%fas%' OR
                        vendor_name ILIKE '%kal%' OR
                        vendor_name ILIKE '%the%' OR
                        vendor_name ILIKE '%tim%' OR
                        vendor_name ILIKE '%real%' OR
                        vendor_name ILIKE '%wok%' OR
                        vendor_name ILIKE '%walmart%' OR
                        vendor_name ILIKE '%bed%' OR
                        vendor_name ILIKE '%tony%'
                    )
            )
""")

updates = []
for receipt_id, vendor_name in cur.fetchall():
    updates.append((receipt_id, vendor_name, '[UNKNOWN POINT OF SALE]'))

dry_run = '--dry-run' in sys.argv or len(sys.argv) == 1

print(f"Found {len(updates)} remaining POINT OF SALE receipts with no vendor name\n")

if dry_run:
    print("Sample (first 10):")
    for receipt_id, vendor, new_vendor in updates[:10]:
        print(f"  {receipt_id:>8} | {vendor[:70]}")
    print(f"\n✅ DRY RUN COMPLETE")
    print("Run with --execute to convert to [UNKNOWN POINT OF SALE]")
else:
    print("⚠️  EXECUTION MODE")
    response = input(f"\nType 'UNKNOWN' to update {len(updates)} receipts to [UNKNOWN POINT OF SALE]: ")
    
    if response != 'UNKNOWN':
        print("❌ Cancelled")
        cur.close()
        conn.close()
        sys.exit(0)
    
    print("\n📝 Converting remaining POINT OF SALE receipts to [UNKNOWN POINT OF SALE]...")
    for receipt_id, vendor_name, new_vendor in updates:
        cur.execute("""
            UPDATE receipts
            SET vendor_name = %s
            WHERE receipt_id = %s
        """, (new_vendor, receipt_id))
    
    conn.commit()
    print(f"   ✅ Updated {len(updates)} receipts")
    print("\n✅ CONVERSION COMPLETE")
    print("Remaining POINT OF SALE receipts are now marked as [UNKNOWN POINT OF SALE]")

cur.close()
conn.close()
