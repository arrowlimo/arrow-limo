#!/usr/bin/env python3
"""
Fix truncated vendor names extracted from POINT OF.
"""

import psycopg2

conn = psycopg2.connect(
    host="localhost",
    database="almsdata",
    user="postgres",
    password="***REMOVED***"
)

cur = conn.cursor()

print("=" * 80)
print("FIXING TRUNCATED VENDOR NAMES")
print("=" * 80)

# Fix truncated names
truncation_fixes = [
    # From POINT OF extractions
    ('ERLES AUTO REPA', 'ERLES AUTO REPAIR'),
    ("GREGG'S PAINT A", "GREGG'S PAINT AND COLLISION"),
    ('NORTHLAND RADIA', 'NORTHLAND RADIATOR'),
    ('TAYLOR VETERINA', 'TAYLOR VETERINARY CLINIC'),
    ('THE TIRE GARAGE', 'THE TIRE GARAGE'),  # Already complete
    ('WESTERNER EXPOS', 'WESTERNER EXPOSITION'),
    ('KIRK\'S TIRE (RE', 'KIRK\'S TIRE (RED DEER)'),
    ('COPIES NOW', 'COPIES NOW'),  # Already complete
    ('RED DEER TOYOTA', 'RED DEER TOYOTA'),  # Already complete
    ('INFINITE INNO', 'INFINITE INNOVATIONS'),
    ('BEST BUY #960', 'BEST BUY'),
    ('RIFCO NATIONAL', 'RIFCO NATIONAL'),  # Already complete
    
    # Other truncated names we've seen
    ('REAL CDN SUPERS', 'REAL CANADIAN SUPERSTORE'),
    ('CHINA BEN RESTA', 'CHINA BEN RESTAURANT'),
    ('GAETZ FRESH MAR', 'GAETZ FRESH MARKET'),
    ('GROWER DIRECT S', 'GROWER DIRECT'),
    ('BAMBOO HUT SOUT', 'BAMBOO HUT'),
    ('BLUE DRAGON FIN', 'BLUE DRAGON FINANCIAL'),
    ('ANDREW SHERET L', 'ANDREW SHERET LIMITED'),
    ('ACTION EQUIPMEN', 'ACTION EQUIPMENT'),
    ('AUTOMOTIVE PART', 'AUTOMOTIVE PARTS'),
    ('BOTTOMS UP COLD', 'BOTTOMS UP COLD BEER'),
    ('BOWDEN REDDI MART', 'BOWDEN REDDI MART'),  # Complete
    ('BOWER PLACE SHO', 'BOWER PLACE SHOPPING CENTRE'),
    ('CHINA BEN RESTAURAN', 'CHINA BEN RESTAURANT'),
    ('CORONATION RESTAURAN', 'CORONATION RESTAURANT'),
    ('GAETZ AVE CENTE', 'GAETZ AVENUE CENTER'),
    ('GAETZ AVENUE PH', 'GAETZ AVENUE PHARMACY'),
]

print("\nApplying truncation fixes:")
total_fixed = 0

for old_name, new_name in truncation_fixes:
    cur.execute("""
        UPDATE receipts
        SET vendor_name = %s
        WHERE vendor_name = %s
    """, (new_name, old_name))
    
    count = cur.rowcount
    if count > 0:
        total_fixed += count
        print(f"  ✅ {count:4} receipts: '{old_name[:35]}' → '{new_name[:35]}'")

conn.commit()

print(f"\n✅ COMMITTED: {total_fixed} receipts updated")

# Also consolidate similar vendors
print("\n" + "=" * 80)
print("CONSOLIDATING SIMILAR VENDORS")
print("=" * 80)

# Check for variations that should be consolidated
consolidations = [
    # ERLES AUTO REPAIR variations
    ('ERLES AUTO REPAIR', [
        'ERLES AUTO REPAIR',
        'ERLES AUTO REPA',
    ]),
    # BEST BUY variations
    ('BEST BUY', [
        'BEST BUY',
        'BEST BUY #960',
        'BEST BUY MOBILE',
    ]),
    # REAL CANADIAN SUPERSTORE variations
    ('REAL CANADIAN SUPERSTORE', [
        'REAL CANADIAN SUPERSTORE',
        'REAL CDN SUPERS',
        'RCSS',
        'SUPERSTORE',
    ]),
]

for target_name, variations in consolidations:
    for variation in variations:
        if variation == target_name:
            continue
        
        cur.execute("""
            UPDATE receipts
            SET vendor_name = %s
            WHERE vendor_name = %s
        """, (target_name, variation))
        
        count = cur.rowcount
        if count > 0:
            total_fixed += count
            print(f"  ✅ {count:4} receipts: '{variation}' → '{target_name}'")

conn.commit()

# Final summary
print("\n" + "=" * 80)
print("SUMMARY")
print("=" * 80)

# Show top vendors after cleanup
cur.execute("""
    SELECT vendor_name, COUNT(*) as count, SUM(gross_amount) as total
    FROM receipts
    GROUP BY vendor_name
    ORDER BY total DESC NULLS LAST
    LIMIT 30
""")

print(f"\nTop 30 vendors after cleanup:")
print(f"{'Vendor':<45} {'Count':>6} {'Total':>15}")
print("-" * 70)

for vendor, count, total in cur.fetchall():
    total_str = f"${total:,.2f}" if total else "$0.00"
    print(f"{vendor[:44]:<45} {count:>6} {total_str:>15}")

cur.close()
conn.close()

print("\n✅ COMPLETE")
