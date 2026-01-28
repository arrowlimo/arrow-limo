#!/usr/bin/env python3
"""
Categorize CO-OP receipts based on linked banking transaction descriptions
CO-OP has multiple business units: Gas Bar, Liquor, HGC (Home & Garden), Store
"""
import psycopg2
import sys

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

def categorize_coop_from_banking(banking_desc):
    """Determine CO-OP business unit from banking description"""
    if not banking_desc:
        return "CO-OP"
    
    desc_upper = banking_desc.upper()
    
    # U-Haul is not CO-OP
    if 'U-HAUL' in desc_upper or 'UHAUL' in desc_upper:
        return "UHAUL RENTAL"
    
    # Gas bar locations: TAYLOR, GAETZ, SYLVAN, DOWNTOWN, BLKFLDS, RED DEE, EASTVIE
    if any(loc in desc_upper for loc in ['TAYLOR', 'GAETZ', 'SYLVAN', 'DOWNTOWN', 'BLKFLDS', 'RED DEE', 'EASTVIE', 'GAETZ G', 'EVERGREEN']):
        return "CO-OP GAS BAR"
    
    # HGC (Home and Garden Centre)
    if 'HGC' in desc_upper or ('HOME' in desc_upper and 'GARDEN' in desc_upper):
        return "CO-OP HGC"
    
    # Liquor
    if 'LIQUOR' in desc_upper or 'WINE' in desc_upper or 'BEER' in desc_upper:
        return "CO-OP LIQUOR"
    
    # Generic store/food
    if 'FOOD' in desc_upper or 'GROCERY' in desc_upper or 'STORE' in desc_upper:
        return "CO-OP STORE"
    
    return "CO-OP"

# Preview mode by default
dry_run = '--dry-run' in sys.argv or len(sys.argv) == 1

# Get all CO-OP receipts with linked banking transactions
cur.execute("""
    SELECT 
        r.receipt_id,
        r.vendor_name,
        bt.description as banking_desc
    FROM receipts r
    LEFT JOIN banking_transactions bt ON r.banking_transaction_id = bt.transaction_id
    WHERE (r.vendor_name ILIKE '%co-op%' OR r.vendor_name ILIKE '%coop%')
      AND r.vendor_name NOT ILIKE '%insurance%'
      AND bt.description IS NOT NULL
    ORDER BY r.receipt_id
""")

updates = []
for receipt_id, vendor_name, banking_desc in cur.fetchall():
    new_vendor = categorize_coop_from_banking(banking_desc)
    if new_vendor != vendor_name:
        updates.append((receipt_id, vendor_name, new_vendor, banking_desc))

print(f"Found {len(updates)} CO-OP receipts to categorize\n")

# Show sample updates
print("Sample updates (first 20):")
print("=" * 120)
for i, (receipt_id, old_vendor, new_vendor, banking_desc) in enumerate(updates[:20]):
    print(f"{old_vendor:<20} → {new_vendor:<20} | {banking_desc[:70]}")

# Category summary
from collections import Counter
category_counts = Counter(new_vendor for _, _, new_vendor, _ in updates)
print("\n" + "=" * 120)
print("CATEGORY SUMMARY")
print("=" * 120)
for category, count in category_counts.most_common():
    print(f"{category:<25}: {count:>5} receipts")

if dry_run:
    print("\n✅ DRY RUN COMPLETE")
    print("Run with --execute to apply categorization")
else:
    print("\n⚠️  EXECUTION MODE")
    response = input(f"\nType 'CATEGORIZE' to update {len(updates)} CO-OP receipts: ")
    
    if response != 'CATEGORIZE':
        print("❌ Cancelled")
        cur.close()
        conn.close()
        sys.exit(0)
    
    print("\n📝 Updating CO-OP receipt categories...")
    for receipt_id, old_vendor, new_vendor, banking_desc in updates:
        cur.execute("""
            UPDATE receipts
            SET vendor_name = %s
            WHERE receipt_id = %s
        """, (new_vendor, receipt_id))
    
    conn.commit()
    print(f"   ✅ Updated {len(updates)} CO-OP receipts")
    print("\n✅ CATEGORIZATION COMPLETE")

cur.close()
conn.close()
