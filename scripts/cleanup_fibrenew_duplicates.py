#!/usr/bin/env python3
"""Remove Fibrenew receipt duplicates - keep one per (date, amount) pair."""

import psycopg2
from collections import defaultdict

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REMOVED***'
)
cur = conn.cursor()

print("="*120)
print("FIBRENEW DUPLICATE CLEANUP")
print("="*120)

# Get all Fibrenew receipts
cur.execute("""
    SELECT receipt_id, receipt_date, vendor_name, gross_amount, description, 
           created_at
    FROM receipts
    WHERE vendor_name ILIKE '%fibrenew%' 
       OR description ILIKE '%fibrenew%'
       OR (category = 'rent' AND vendor_name ILIKE '%office rent%')
    ORDER BY receipt_date, gross_amount, receipt_id
""")

receipts = cur.fetchall()
print(f"\nTotal receipts: {len(receipts)}")

# Group by (date, amount)
groups = defaultdict(list)
for r in receipts:
    key = (r[1], r[3])
    groups[key].append(r)

# Find duplicates - keep oldest receipt_id (lowest ID = first import)
duplicates_to_delete = []
for key, recs in groups.items():
    if len(recs) > 1:
        # Sort by created_at, then receipt_id
        sorted_recs = sorted(recs, key=lambda x: (x[5] or '9999-99-99', x[0]))
        # Keep first, delete rest
        to_keep = sorted_recs[0]
        to_delete = sorted_recs[1:]
        duplicates_to_delete.extend([r[0] for r in to_delete])
        
        print(f"\n{key[0]} | ${key[1]:.2f} - Keeping ID {to_keep[0]}, deleting {len(to_delete)} duplicates")

print(f"\n{'='*120}")
print(f"SUMMARY: {len(duplicates_to_delete)} duplicate receipts to delete")
print(f"{'='*120}")

if duplicates_to_delete:
    # Create backup first
    timestamp = __import__('datetime').datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_table = f'receipts_fibrenew_backup_{timestamp}'
    
    print(f"\nCreating backup: {backup_table}")
    cur.execute(f"""
        CREATE TABLE {backup_table} AS
        SELECT * FROM receipts
        WHERE receipt_id = ANY(%s)
    """, (duplicates_to_delete,))
    
    print(f"Backup created with {cur.rowcount} rows")
    
    # Delete duplicates
    print(f"\nDeleting {len(duplicates_to_delete)} duplicate receipts...")
    cur.execute("""
        DELETE FROM receipts
        WHERE receipt_id = ANY(%s)
    """, (duplicates_to_delete,))
    
    deleted_count = cur.rowcount
    print(f"✓ Deleted {deleted_count} duplicate receipts")
    
    conn.commit()
    
    # Verify cleanup
    cur.execute("""
        SELECT COUNT(*) FROM receipts
        WHERE vendor_name ILIKE '%fibrenew%' 
           OR description ILIKE '%fibrenew%'
           OR (category = 'rent' AND vendor_name ILIKE '%office rent%')
    """)
    remaining = cur.fetchone()[0]
    
    print(f"\nRemaining Fibrenew receipts: {remaining}")
    print(f"Removed: {len(receipts) - remaining} receipts")
    
    # Calculate corrected total
    cur.execute("""
        SELECT SUM(gross_amount) FROM receipts
        WHERE vendor_name ILIKE '%fibrenew%' 
           OR description ILIKE '%fibrenew%'
           OR (category = 'rent' AND vendor_name ILIKE '%office rent%')
    """)
    corrected_total = cur.fetchone()[0]
    
    print(f"\nCorrected total Fibrenew payments: ${corrected_total:,.2f}")
    print(f"Original total (with duplicates): $243,860.29")
    print(f"Duplicate amount removed: ${243860.29 - corrected_total:,.2f}")
else:
    print("\n✅ No duplicates found")

conn.close()
