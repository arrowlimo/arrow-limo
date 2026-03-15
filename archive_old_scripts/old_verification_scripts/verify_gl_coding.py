#!/usr/bin/env python3
"""Verify receipt GL coding - identify potentially miscoded receipts."""

import psycopg2

conn = psycopg2.connect(
    host='localhost',
    user='postgres',
    password='ArrowLimousine',
    dbname='almsdata'
)
cur = conn.cursor()

print("\n" + "="*100)
print("GL CODING VERIFICATION - IDENTIFYING RECEIPTS NEEDING REVIEW")
print("="*100)

# 1. Receipts without GL codes
print("\n1. RECEIPTS WITHOUT GL CODES (Need coding)")
print("-"*100)

cur.execute("""
    SELECT 
        vendor_name,
        COUNT(*) as count,
        SUM(gross_amount) as total
    FROM receipts
    WHERE gl_account_code IS NULL OR gl_account_code = ''
    GROUP BY vendor_name
    ORDER BY count DESC
""")

uncoded = cur.fetchall()
print(f"Total uncoded: {sum(r[1] for r in uncoded):,} receipts, ${sum(r[2] for r in uncoded):,.2f}")
print(f"\n{'Vendor':<45} {'Count':<10} {'Total $'}")
print("-"*100)

for vendor, count, total in uncoded[:20]:
    vendor_display = (vendor or "BLANK")[:45]
    print(f"{vendor_display:<45} {count:<10} ${total:,.2f}")

# 2. Fuel stations - check for potential split receipts
print("\n" + "="*100)
print("2. FUEL STATION RECEIPTS - Check for food/beverage purchases")
print("="*100)
print("(These should be split: fuel→5200, food/drinks→5116 or personal)")
print("-"*100)

cur.execute("""
    SELECT 
        receipt_id,
        receipt_date,
        vendor_name,
        gl_account_code,
        gross_amount,
        description
    FROM receipts
    WHERE (
        vendor_name ILIKE '%shell%'
        OR vendor_name ILIKE '%esso%'
        OR vendor_name ILIKE '%petro%canada%'
        OR vendor_name ILIKE '%fas gas%'
        OR vendor_name ILIKE '%husky%'
        OR vendor_name ILIKE '%7-eleven%'
        OR vendor_name ILIKE '%circle k%'
        OR vendor_name ILIKE '%co-op%gas%'
        OR vendor_name ILIKE '%chevron%'
    )
    AND gl_account_code IS NOT NULL
    AND (
        description ILIKE '%food%'
        OR description ILIKE '%beverage%'
        OR description ILIKE '%coffee%'
        OR description ILIKE '%snack%'
        OR description ILIKE '%drink%'
        OR gross_amount > 100  -- Large fuel station purchases might include convenience items
    )
    ORDER BY receipt_date DESC
    LIMIT 50
""")

fuel_potential = cur.fetchall()
if fuel_potential:
    print(f"Found {len(fuel_potential)} fuel station receipts to review:")
    print(f"{'ID':<8} {'Date':<12} {'Vendor':<30} {'GL':<10} {'Amount':<12} {'Description'}")
    print("-"*100)
    for receipt_id, date, vendor, gl_code, amount, desc in fuel_potential[:25]:
        vendor_display = (vendor or "")[:30]
        desc_display = (desc or "")[:40]
        print(f"{receipt_id:<8} {str(date):<12} {vendor_display:<30} {gl_code or 'N/A':<10} ${amount:<11,.2f} {desc_display}")
else:
    print("No fuel station receipts with food/beverage indicators found")

# 3. Food/Beverage vendors - should be client amenities or meals
print("\n" + "="*100)
print("3. FOOD/BEVERAGE VENDORS - Verify GL coding")
print("="*100)
print("Expected codes: 5116 (Client Amenities), 5320 (Driver Meals), 5325 (Business Meals)")
print("-"*100)

cur.execute("""
    SELECT 
        vendor_name,
        gl_account_code,
        gl_account_name,
        COUNT(*) as count,
        SUM(gross_amount) as total
    FROM receipts
    WHERE (
        vendor_name ILIKE '%tim horton%'
        OR vendor_name ILIKE '%starbucks%'
        OR vendor_name ILIKE '%mcdonald%'
        OR vendor_name ILIKE '%subway%'
        OR vendor_name ILIKE '%coffee%'
        OR vendor_name ILIKE '%pizza%'
        OR vendor_name ILIKE '%restaurant%'
        OR vendor_name ILIKE '%bar %'
        OR vendor_name ILIKE '%pub%'
        OR vendor_name ILIKE '%diner%'
        OR vendor_name ILIKE '%cafe%'
    )
    AND gl_account_code IS NOT NULL
    GROUP BY vendor_name, gl_account_code, gl_account_name
    ORDER BY count DESC
""")

food_vendors = cur.fetchall()
if food_vendors:
    print(f"{'Vendor':<35} {'GL':<10} {'GL Name':<30} {'Cnt':<6} {'Total $'}")
    print("-"*100)
    
    potential_issues = []
    for vendor, gl_code, gl_name, count, total in food_vendors:
        vendor_display = (vendor or "")[:35]
        gl_name_display = (gl_name or "")[:30]
        print(f"{vendor_display:<35} {gl_code:<10} {gl_name_display:<30} {count:<6} ${total:,.2f}")
        
        # Flag if not coded to expected GL accounts
        if gl_code not in ('5116', '5320', '5325', '5315', '5310', '5900', '9999'):
            potential_issues.append((vendor, gl_code, count, total))
    
    if potential_issues:
        print(f"\n⚠ POTENTIAL MISCODING - Food/beverage vendors not coded to expected accounts:")
        for vendor, gl_code, count, total in potential_issues:
            print(f"  {vendor[:40]} → GL {gl_code} ({count} receipts, ${total:,.2f})")
else:
    print("No food/beverage vendor receipts found")

# 4. Liquor/alcohol purchases - should be client amenities or personal
print("\n" + "="*100)
print("4. LIQUOR/ALCOHOL PURCHASES")
print("="*100)
print("Expected codes: 5116 (Client Amenities if for clients), 9999 (Personal)")
print("-"*100)

cur.execute("""
    SELECT 
        vendor_name,
        gl_account_code,
        gl_account_name,
        COUNT(*) as count,
        SUM(gross_amount) as total
    FROM receipts
    WHERE (
        vendor_name ILIKE '%liquor%'
        OR vendor_name ILIKE '%wine%'
        OR vendor_name ILIKE '%beer%'
        OR vendor_name ILIKE '%spirits%'
        OR vendor_name ILIKE '%alcoh%'
    )
    AND gl_account_code IS NOT NULL
    GROUP BY vendor_name, gl_account_code, gl_account_name
    ORDER BY count DESC
""")

liquor_vendors = cur.fetchall()
if liquor_vendors:
    print(f"{'Vendor':<35} {'GL':<10} {'GL Name':<30} {'Cnt':<6} {'Total $'}")
    print("-"*100)
    for vendor, gl_code, gl_name, count, total in liquor_vendors:
        vendor_display = (vendor or "")[:35]
        gl_name_display = (gl_name or "")[:30]
        print(f"{vendor_display:<35} {gl_code:<10} {gl_name_display:<30} {count:<6} ${total:,.2f}")
else:
    print("No liquor purchase receipts found")

# 5. Grocery stores - likely split between client amenities and personal
print("\n" + "="*100)
print("5. GROCERY STORE PURCHASES")
print("="*100)
print("Expected codes: 5116 (Client Amenities), 5320 (Driver meals), 9999 (Personal)")
print("-"*100)

cur.execute("""
    SELECT 
        vendor_name,
        gl_account_code,
        gl_account_name,
        COUNT(*) as count,
        SUM(gross_amount) as total
    FROM receipts
    WHERE (
        vendor_name ILIKE '%safeway%'
        OR vendor_name ILIKE '%sobeys%'
        OR vendor_name ILIKE '%save-on%'
        OR vendor_name ILIKE '%superstore%'
        OR vendor_name ILIKE '%walmart%'
        OR vendor_name ILIKE '%costco%'
        OR vendor_name ILIKE '%no frills%'
    )
    AND gl_account_code IS NOT NULL
    GROUP BY vendor_name, gl_account_code, gl_account_name
    ORDER BY count DESC
""")

grocery_vendors = cur.fetchall()
if grocery_vendors:
    print(f"{'Vendor':<35} {'GL':<10} {'GL Name':<30} {'Cnt':<6} {'Total $'}")
    print("-"*100)
    for vendor, gl_code, gl_name, count, total in grocery_vendors:
        vendor_display = (vendor or "")[:35]
        gl_name_display = (gl_name or "")[:30]
        print(f"{vendor_display:<35} {gl_code:<10} {gl_name_display:<30} {count:<6} ${total:,.2f}")
else:
    print("No grocery store receipts found")

# 6. Check GL codes that shouldn't exist or are blank
print("\n" + "="*100)
print("6. PROBLEMATIC GL CODES")
print("="*100)

cur.execute("""
    SELECT 
        gl_account_code,
        gl_account_name,
        COUNT(*) as count,
        SUM(gross_amount) as total
    FROM receipts
    WHERE gl_account_code IS NOT NULL
    AND (
        gl_account_code = ''
        OR gl_account_code = '6900'  -- Generic/miscellaneous
        OR gl_account_code = '5900'  -- Generic/miscellaneous
        OR gl_account_name IS NULL
        OR gl_account_name = ''
    )
    GROUP BY gl_account_code, gl_account_name
    ORDER BY count DESC
""")

problematic = cur.fetchall()
if problematic:
    print("GL codes that need specific recoding:")
    print(f"{'GL Code':<12} {'GL Name':<40} {'Count':<10} {'Total $'}")
    print("-"*100)
    for gl_code, gl_name, count, total in problematic:
        gl_name_display = (gl_name or "NO NAME")[:40]
        print(f"{gl_code or 'BLANK':<12} {gl_name_display:<40} {count:<10} ${total:,.2f}")

# 7. Summary
print("\n" + "="*100)
print("SUMMARY & NEXT STEPS")
print("="*100)

cur.execute("SELECT COUNT(*) FROM receipts WHERE gl_account_code IS NOT NULL")
total_coded = cur.fetchone()[0]

cur.execute("SELECT COUNT(*) FROM receipts WHERE gl_account_code IS NULL OR gl_account_code = ''")
total_uncoded = cur.fetchone()[0]

print(f"""
Total receipts: {total_coded + total_uncoded:,}
  With GL codes: {total_coded:,}
  Without GL codes: {total_uncoded:,}

ACTIONS NEEDED:
1. Code {total_uncoded:,} receipts without GL codes
2. Review fuel station receipts for split purchases (fuel vs convenience items)
3. Verify food/beverage vendors are coded to correct GL accounts
4. Review generic GL codes (6900, 5900) for proper categorization
5. Consider implementing split receipt functionality for mixed purchases

GL CODE REFERENCE:
- 5200: Fuel on Road (fuel only)
- 5116: Client Amenities (food, coffee, beverages for clients)
- 5320: Driver Meals - On Duty (meals for drivers during charters)
- 5325: Business Meals & Entertainment (50% deductible)
- 5315: Beverages - Business Entertainment
- 9999: Personal Draws (owner personal purchases)
""")

conn.close()
