#!/usr/bin/env python3
"""Recode food and beverage vendors to proper GL accounts."""

import psycopg2

conn = psycopg2.connect(
    host='localhost',
    user='postgres',
    password='ArrowLimousine',
    dbname='almsdata'
)
cur = conn.cursor()

print("\n" + "="*100)
print("RECODE FOOD/BEVERAGE VENDORS TO PROPER GL CODES")
print("="*100)

# Food/beverage should be coded to:
# - 5116: Client Amenities (food/coffee for clients)
# - 5320: Driver Meals - On Duty (meals for drivers during work)
# - 5325: Business Meals & Entertainment (business meetings, 50% deductible)

updates_summary = []

# 1. Tim Hortons → GL 5116 (Client Amenities)
print("\n1. Recoding Tim Hortons to GL 5116 (Client Amenities)...")
print("-"*100)

cur.execute("""
    UPDATE receipts
    SET gl_account_code = '5116',
        gl_account_name = 'Client Amenities - Food, Coffee, Supplies'
    WHERE vendor_name ILIKE '%tim horton%'
    AND gl_account_code NOT IN ('5116', '5320', '5325', '9999')
""")

tim_hortons_updated = cur.rowcount
if tim_hortons_updated > 0:
    print(f"✓ Updated {tim_hortons_updated} Tim Hortons receipts")
    updates_summary.append(('Tim Hortons', tim_hortons_updated, '5116'))

# 2. Starbucks → GL 5116 (Client Amenities)
cur.execute("""
    UPDATE receipts
    SET gl_account_code = '5116',
        gl_account_name = 'Client Amenities - Food, Coffee, Supplies'
    WHERE vendor_name ILIKE '%starbucks%'
    AND gl_account_code NOT IN ('5116', '5320', '5325', '9999')
""")

starbucks_updated = cur.rowcount
if starbucks_updated > 0:
    print(f"✓ Updated {starbucks_updated} Starbucks receipts")
    updates_summary.append(('Starbucks', starbucks_updated, '5116'))

# 3. Pizza & Restaurants → GL 5116 (Client Amenities) - assuming for clients
print("\n2. Recoding restaurants to GL 5116 (Client Amenities)...")
print("-"*100)

restaurant_vendors = [
    "%pizza%",
    "%george's%steak%",
    "%jds%bar%grill%",
    "%phil%restaurant%",
    "%boston%pizza%",
    "%subway%",
    "%bar%burrito%",
    "%mcdonald%"
]

for pattern in restaurant_vendors:
    cur.execute(f"""
        UPDATE receipts
        SET gl_account_code = '5116',
            gl_account_name = 'Client Amenities - Food, Coffee, Supplies'
        WHERE vendor_name ILIKE %s
        AND gl_account_code NOT IN ('5116', '5320', '5325', '5315', '9999')
    """, (pattern,))
    
    if cur.rowcount > 0:
        vendor_name = pattern.replace('%', '').replace('_', ' ').title()
        print(f"✓ Updated {cur.rowcount} {vendor_name} receipts")
        updates_summary.append((vendor_name, cur.rowcount, '5116'))

# 4. Liquor→ GL 5116 (Client Amenities) or 5315 (Business Entertainment)
print("\n3. Recoding liquor purchases to GL 5116 (Client Amenities)...")
print("-"*100)

cur.execute("""
    UPDATE receipts
    SET gl_account_code = '5116',
        gl_account_name = 'Client Amenities - Food, Coffee, Supplies'
    WHERE (vendor_name ILIKE '%liquor%' OR vendor_name ILIKE '%wine%')
    AND gl_account_code NOT IN ('5116', '5315', '5310', '9999')
    AND gross_amount < 500  -- Large purchases might be business events
""")

liquor_updated = cur.rowcount
if liquor_updated > 0:
    print(f"✓ Updated {liquor_updated} smaller liquor purchases to Client Amenities")
    updates_summary.append(('Liquor (small)', liquor_updated, '5116'))

# Large liquor purchases → GL 5315 (Business Entertainment)
cur.execute("""
    UPDATE receipts
    SET gl_account_code = '5315',
        gl_account_name = 'Beverages - Business Entertainment'
    WHERE (vendor_name ILIKE '%liquor%' OR vendor_name ILIKE '%wine%')
    AND gl_account_code NOT IN ('5116', '5315', '5310', '9999')
    AND gross_amount >= 500
""")

liquor_large_updated = cur.rowcount
if liquor_large_updated > 0:
    print(f"✓ Updated {liquor_large_updated} larger liquor purchases to Business Entertainment")
    updates_summary.append(('Liquor (large)', liquor_large_updated, '5315'))

conn.commit()

# 5. Summary
print("\n" + "="*100)
print("SUMMARY OF UPDATES")
print("="*100)

total_updated = sum([count for _, count, _ in updates_summary])

print(f"\n{'Vendor Category':<30} {'Receipts Updated':<20} {'New GL Code'}")
print("-"*100)

for vendor, count, gl_code in updates_summary:
    print(f"{vendor:<30} {count:<20} {gl_code}")

print("-"*100)
print(f"{'TOTAL':<30} {total_updated:<20}")

# 6. Verification
print("\n" + "="*100)
print("VERIFICATION - Food/Beverage by GL Code")
print("="*100)

cur.execute("""
    SELECT 
        gl_account_code,
        gl_account_name,
        COUNT(*) as count,
        SUM(gross_amount) as total
    FROM receipts
    WHERE (
        vendor_name ILIKE '%tim horton%'
        OR vendor_name ILIKE '%starbucks%'
        OR vendor_name ILIKE '%pizza%'
        OR vendor_name ILIKE '%restaurant%'
        OR vendor_name ILIKE '%mcdonald%'
        OR vendor_name ILIKE '%liquor%'
    )
    GROUP BY gl_account_code, gl_account_name
    ORDER BY count DESC
""")

print(f"{'GL Code':<10} {'GL Name':<45} {'Count':<10} {'Total $'}")
print("-"*100)

for gl_code, gl_name, count, total in cur.fetchall():
    gl_name_display = (gl_name or "NO NAME")[:45]
    total_str = f"${total:,.2f}" if total else "$0.00"
    print(f"{gl_code or 'NONE':<10} {gl_name_display:<45} {count:<10} {total_str}")

print("\n" + "="*100)
print("COMPLETE")
print("="*100)
print(f"""
✓ Recoded {total_updated:,} food/beverage vendor receipts
✓ Properly categorized for tax deductibility
✓ Client amenities → GL 5116
✓ Business entertainment → GL 5315
""")

conn.close()
