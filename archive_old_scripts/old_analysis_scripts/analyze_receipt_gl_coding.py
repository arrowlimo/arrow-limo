#!/usr/bin/env python3
"""Analyze receipt GL coding and identify split receipts that need attention."""

import psycopg2
from collections import defaultdict

conn = psycopg2.connect(
    host='localhost',
    user='postgres',
    password='ArrowLimousine',
    dbname='almsdata'
)
cur = conn.cursor()

print("\n" + "="*100)
print("RECEIPT GL CODE ANALYSIS")
print("="*100)

# 1. Get GL code distribution
print("\n1. GL CODE USAGE BY RECEIPT COUNT AND AMOUNT")
print("-"*100)

cur.execute("""
    SELECT 
        gl_account_code,
        gl_account_name,
        COUNT(*) as receipt_count,
        SUM(gross_amount) as total_amount,
        SUM(CASE WHEN owner_personal_amount > 0 THEN 1 ELSE 0 END) as split_count
    FROM receipts
    WHERE gl_account_code IS NOT NULL
    GROUP BY gl_account_code, gl_account_name
    ORDER BY receipt_count DESC
""")

print(f"{'GL Code':<10} {'GL Name':<45} {'Receipts':<10} {'Total $':<15} {'Splits':<8}")
print("-"*100)

total_receipts = 0
total_amount = 0
for code, name, count, amount, splits in cur.fetchall():
    total_receipts += count
    total_amount += amount or 0
    amount_str = f"${amount:,.2f}" if amount else "$0.00"
    name_display = (name or "")[:45]
    print(f"{code:<10} {name_display:<45} {count:<10} {amount_str:<15} {splits:<8}")

print("-"*100)
print(f"{'TOTAL':<10} {'':<45} {total_receipts:<10} ${total_amount:,.2f}")

# 2. Check for receipts without GL codes
print("\n" + "="*100)
print("2. RECEIPTS WITHOUT GL CODES")
print("="*100)

cur.execute("""
    SELECT 
        COUNT(*) as count,
        SUM(gross_amount) as total
    FROM receipts
    WHERE gl_account_code IS NULL
""")

no_gl_count, no_gl_total = cur.fetchone()
print(f"Receipts without GL code: {no_gl_count:,} (${no_gl_total:,.2f})")

if no_gl_count > 0:
    # Show vendors with most uncoded receipts
    cur.execute("""
        SELECT 
            vendor_name,
            COUNT(*) as count,
            SUM(gross_amount) as total
        FROM receipts
        WHERE gl_account_code IS NULL
        GROUP BY vendor_name
        ORDER BY count DESC
        LIMIT 20
    """)
    
    print(f"\nTop vendors without GL codes:")
    print(f"{'Vendor':<40} {'Count':<10} {'Total $'}")
    print("-"*100)
    for vendor, count, total in cur.fetchall():
        vendor_display = (vendor or "")[:40]
        print(f"{vendor_display:<40} {count:<10} ${total:,.2f}")

# 3. Analyze SPLIT RECEIPTS (owner_personal_amount > 0)
print("\n" + "="*100)
print("3. SPLIT RECEIPTS ANALYSIS")
print("="*100)

cur.execute("""
    SELECT 
        COUNT(*) as count,
        SUM(gross_amount) as total_gross,
        SUM(owner_personal_amount) as total_personal,
        SUM(gross_amount - owner_personal_amount) as total_business
    FROM receipts
    WHERE owner_personal_amount > 0
""")

split_count, total_gross, total_personal, total_business = cur.fetchone()
print(f"Total split receipts: {split_count:,}")
if split_count > 0:
    print(f"  Total gross amount: ${total_gross:,.2f}")
    print(f"  Personal portion: ${total_personal:,.2f}")
    print(f"  Business portion: ${total_business:,.2f}")
else:
    print("  (No split receipts found - owner_personal_amount not used)")

# 4. Split receipts by GL code
print("\n4. SPLIT RECEIPTS BY GL CODE")
print("-"*100)

cur.execute("""
    SELECT 
        gl_account_code,
        gl_account_name,
        vendor_name,
        COUNT(*) as count,
        SUM(gross_amount) as total_gross,
        SUM(owner_personal_amount) as total_personal
    FROM receipts
    WHERE owner_personal_amount > 0
    GROUP BY gl_account_code, gl_account_name, vendor_name
    ORDER BY count DESC
    LIMIT 30
""")

print(f"{'GL Code':<10} {'GL Name':<30} {'Vendor':<25} {'Cnt':<6} {'Gross $':<12} {'Personal $'}")
print("-"*100)

for code, name, vendor, count, gross, personal in cur.fetchall():
    code_display = code or "NO CODE"
    name_display = (name or "")[:30]
    vendor_display = (vendor or "")[:25]
    print(f"{code_display:<10} {name_display:<30} {vendor_display:<25} {count:<6} ${gross:,.2f}  ${personal:,.2f}")

# 5. Check for fuel GL codes with split receipts (potential miscoding)
print("\n" + "="*100)
print("5. POTENTIAL MISCODED SPLIT RECEIPTS (Fuel stations with personal splits)")
print("="*100)

cur.execute("""
    SELECT 
        receipt_id,
        receipt_date,
        vendor_name,
        gl_account_code,
        gl_account_name,
        gross_amount,
        owner_personal_amount,
        description
    FROM receipts
    WHERE owner_personal_amount > 0
    AND (
        vendor_name ILIKE '%gas%'
        OR vendor_name ILIKE '%petro%'
        OR vendor_name ILIKE '%shell%'
        OR vendor_name ILIKE '%esso%'
        OR vendor_name ILIKE '%husky%'
        OR vendor_name ILIKE '%7-eleven%'
        OR vendor_name ILIKE '%circle k%'
        OR vendor_name ILIKE '%fas gas%'
        OR vendor_name ILIKE '%co-op%'
        OR gl_account_code IN ('5200', '5110')  -- Fuel GL codes
    )
    ORDER BY receipt_date DESC
    LIMIT 50
""")

fuel_splits = cur.fetchall()
if fuel_splits:
    print(f"\nFound {len(fuel_splits)} fuel station receipts with personal splits:")
    print(f"{'ID':<8} {'Date':<12} {'Vendor':<25} {'GL':<10} {'Gross':<12} {'Personal':<12} {'Desc'}")
    print("-"*100)
    
    for receipt_id, date, vendor, gl_code, gl_name, gross, personal, desc in fuel_splits[:25]:
        vendor_display = (vendor or "")[:25]
        desc_display = (desc or "")[:30]
        print(f"{receipt_id:<8} {str(date):<12} {vendor_display:<25} {gl_code or 'N/A':<10} ${gross:<11,.2f} ${personal:<11,.2f} {desc_display}")
    
    if len(fuel_splits) > 25:
        print(f"\n... and {len(fuel_splits) - 25} more")
else:
    print("No fuel station split receipts found (good!)")

# 6. Check for common split receipt vendors that should have specific GL codes
print("\n" + "="*100)
print("6. COMMON SPLIT RECEIPT VENDORS (Food/Beverage for clients/drivers)")
print("="*100)

cur.execute("""
    SELECT 
        vendor_name,
        gl_account_code,
        COUNT(*) as count,
        SUM(gross_amount) as total_gross,
        SUM(owner_personal_amount) as total_personal
    FROM receipts
    WHERE owner_personal_amount > 0
    AND (
        vendor_name ILIKE '%tim horton%'
        OR vendor_name ILIKE '%starbucks%'
        OR vendor_name ILIKE '%mcdonald%'
        OR vendor_name ILIKE '%subway%'
        OR vendor_name ILIKE '%restaurant%'
        OR vendor_name ILIKE '%coffee%'
        OR vendor_name ILIKE '%safeway%'
        OR vendor_name ILIKE '%sobeys%'
        OR vendor_name ILIKE '%superstore%'
        OR vendor_name ILIKE '%liquor%'
    )
    GROUP BY vendor_name, gl_account_code
    ORDER BY count DESC
    LIMIT 30
""")

food_splits = cur.fetchall()
if food_splits:
    print(f"{'Vendor':<35} {'GL Code':<12} {'Count':<8} {'Gross $':<12} {'Personal $'}")
    print("-"*100)
    for vendor, gl_code, count, gross, personal in food_splits:
        vendor_display = (vendor or "")[:35]
        gl_display = gl_code or "NO CODE"
        print(f"{vendor_display:<35} {gl_display:<12} {count:<8} ${gross:<11,.2f} ${personal:<11,.2f}")
else:
    print("No food/beverage split receipts found")

# 7. Summary and recommendations
print("\n" + "="*100)
print("7. SUMMARY & RECOMMENDATIONS")
print("="*100)

print(f"""
Total receipts analyzed: {total_receipts:,}
Total with GL codes: {total_receipts:,}
Total without GL codes: {no_gl_count:,}
Total split receipts: {split_count:,}

CODING RULES TO VERIFY:
1. Fuel station receipts with personal splits → Should be coded:
   - Business fuel portion → GL 5200 (Fuel on Road)
   - Personal portion (food, drinks) → Owner Personal or specific GL

2. Food/Beverage for clients → GL 5116 (Client Amenities)
   - Tim Hortons, Starbucks for client service
   - NOT coded as fuel

3. Driver meals on long trips → GL 5325 (Meals & Entertainment, 50% deductible)
   - McDonald's, Subway during charters
   - NOT coded as fuel

4. Personal purchases → Owner Personal (GL 5880 or separate)
   - Should have owner_personal_amount set
   - NOT included in business expenses

Next steps:
- Review split receipts at fuel stations
- Verify food/beverage coding
- Check for miscoded personal expenses
""")

conn.close()
