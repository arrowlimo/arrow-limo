"""
PHASE 6: Final Stragglers
Target last identifiable patterns
"""

import psycopg2

conn = psycopg2.connect(
    dbname="almsdata",
    user="postgres",
    password="ArrowLimousine",
    host="localhost"
)
conn.autocommit = False
cur = conn.cursor()

print("="*80)
print("PHASE 6: FINAL STRAGGLERS")
print("="*80)

try:
    # Count uncategorized
    cur.execute("""
        SELECT COUNT(*), SUM(gross_amount)
        FROM receipts
        WHERE category IN ('None', 'Unknown', 'BANKING', 'TRANSFERS', 'NULL') OR category IS NULL
    """)
    
    before_count, before_amount = cur.fetchone()
    print(f"\nUncategorized before: {before_count:,} (${before_amount:,.2f})")
    
    print("\n" + "="*80)
    print("CATEGORIZATION UPDATES")
    print("="*80)
    
    # 1. Red Deer Registries (government fees)
    cur.execute("""
        UPDATE receipts
        SET category = 'Government Fees', updated_at = NOW()
        WHERE (category IN ('None', 'Unknown', 'BANKING', 'TRANSFERS', 'NULL') OR category IS NULL)
          AND vendor_name ILIKE '%RED DEER REGIST%'
    """)
    registries = cur.rowcount
    print(f"1. Red Deer Registries: {registries:,} receipts")
    
    # 2. More driver expenses (EMAIL TRANSFER)
    cur.execute("""
        UPDATE receipts
        SET category = 'Driver Expense', updated_at = NOW()
        WHERE (category IN ('None', 'Unknown', 'BANKING', 'TRANSFERS', 'NULL') OR category IS NULL)
          AND (vendor_name ILIKE '%EMAIL TRANSFER - CHANN%'
               OR vendor_name ILIKE '%EMAIL TRANSFER - ALANNA%'
               OR vendor_name ILIKE '%EMAIL TRANSFER - GOODRICK%'
               OR vendor_name ILIKE '%EMAIL TRANSFER - MANZ%')
    """)
    email_transfers = cur.rowcount
    print(f"2. More EMAIL TRANSFER (Driver Exp): {email_transfers:,} receipts")
    
    # 3. Fast food/restaurants (meals & entertainment)
    cur.execute("""
        UPDATE receipts
        SET category = 'Meals & Entertainment', updated_at = NOW()
        WHERE (category IN ('None', 'Unknown', 'BANKING', 'TRANSFERS', 'NULL') OR category IS NULL)
          AND (vendor_name ILIKE '%WENDY''S%'
               OR vendor_name ILIKE '%DAIRY QUEEN%'
               OR vendor_name ILIKE '%A&W%'
               OR vendor_name ILIKE '%BURGER%'
               OR vendor_name ILIKE '%KFC%')
    """)
    fast_food = cur.rowcount
    print(f"3. Fast Food (Meals): {fast_food:,} receipts")
    
    # 4. Dollar stores/supplies
    cur.execute("""
        UPDATE receipts
        SET category = 'Supplies', updated_at = NOW()
        WHERE (category IN ('None', 'Unknown', 'BANKING', 'TRANSFERS', 'NULL') OR category IS NULL)
          AND (vendor_name ILIKE '%BUCK OR TWO%'
               OR vendor_name ILIKE '%DOLLAR%'
               OR vendor_name ILIKE '%DOLLARAMA%')
    """)
    dollar_stores = cur.rowcount
    print(f"4. Dollar Stores (Supplies): {dollar_stores:,} receipts")
    
    # 5. More vehicle maintenance (car wash)
    cur.execute("""
        UPDATE receipts
        SET category = 'Vehicle Maintenance', updated_at = NOW()
        WHERE (category IN ('None', 'Unknown', 'BANKING', 'TRANSFERS', 'NULL') OR category IS NULL)
          AND (vendor_name ILIKE '%MR.SUDS%'
               OR vendor_name ILIKE '%MR SUDS%'
               OR vendor_name ILIKE '%CARWASH%')
    """)
    car_wash = cur.rowcount
    print(f"5. Car Wash (Maintenance): {car_wash:,} receipts")
    
    # 6. More fuel (FGP codes)
    cur.execute("""
        UPDATE receipts
        SET category = 'Fuel', updated_at = NOW()
        WHERE (category IN ('None', 'Unknown', 'BANKING', 'TRANSFERS', 'NULL') OR category IS NULL)
          AND vendor_name ILIKE '%FGP%'
    """)
    fgp_fuel = cur.rowcount
    print(f"6. More Fuel (FGP): {fgp_fuel:,} receipts")
    
    # 7. Assign "BANKING" categorized receipts to proper Unknown bucket
    # (These are legitimate but we can't identify the category)
    cur.execute("""
        UPDATE receipts
        SET category = 'Unknown', updated_at = NOW()
        WHERE category = 'BANKING'
    """)
    banking_to_unknown = cur.rowcount
    print(f"7. BANKING → Unknown: {banking_to_unknown:,} receipts")
    
    # 8. Assign remaining NULL to Unknown
    cur.execute("""
        UPDATE receipts
        SET category = 'Unknown', updated_at = NOW()
        WHERE category = 'NULL' OR category = 'None'
    """)
    null_to_unknown = cur.rowcount
    print(f"8. NULL/None → Unknown: {null_to_unknown:,} receipts")
    
    total_categorized = registries + email_transfers + fast_food + dollar_stores + car_wash + fgp_fuel
    total_renamed = banking_to_unknown + null_to_unknown
    
    print(f"\n📊 Newly categorized: {total_categorized:,} receipts")
    print(f"📊 Renamed to Unknown: {total_renamed:,} receipts")
    
    # Check final state
    cur.execute("""
        SELECT COUNT(*), SUM(gross_amount)
        FROM receipts
        WHERE category IN ('TRANSFERS') OR category IS NULL
    """)
    
    after_count, after_amount = cur.fetchone()
    
    print("\n" + "="*80)
    print("FINAL RESULTS")
    print("="*80)
    
    # Overall stats
    cur.execute("SELECT COUNT(*), SUM(gross_amount) FROM receipts")
    total_receipts, total_amount = cur.fetchone()
    
    cur.execute("""
        SELECT COUNT(*), SUM(gross_amount)
        FROM receipts
        WHERE category NOT IN ('Unknown', 'TRANSFERS') AND category IS NOT NULL
    """)
    categorized_receipts, categorized_amount = cur.fetchone()
    
    cur.execute("""
        SELECT COUNT(*), SUM(gross_amount)
        FROM receipts
        WHERE category = 'Unknown'
    """)
    unknown_receipts, unknown_amount = cur.fetchone()
    
    cur.execute("""
        SELECT COUNT(*), SUM(gross_amount)
        FROM receipts
        WHERE category = 'TRANSFERS' OR category IS NULL
    """)
    transfers_receipts, transfers_amount = cur.fetchone()
    
    print(f"\nTotal receipts: {total_receipts:,} (${total_amount:,.2f})")
    print(f"\n✅ Fully categorized: {categorized_receipts:,} ({categorized_receipts/total_receipts*100:.1f}%)")
    print(f"   Amount: ${categorized_amount:,.2f}")
    print(f"\n⚠️  Unknown category: {unknown_receipts:,} ({unknown_receipts/total_receipts*100:.1f}%)")
    print(f"   Amount: ${unknown_amount:,.2f}")
    print(f"\n❌ Still TRANSFERS/NULL: {transfers_receipts:,} ({transfers_receipts/total_receipts*100:.1f}%)")
    print(f"   Amount: ${transfers_amount:,.2f}")
    
    # Show top categories
    print("\n" + "="*80)
    print("TOP 20 CATEGORIES")
    print("="*80)
    
    cur.execute("""
        SELECT 
            category,
            COUNT(*) as count,
            SUM(gross_amount) as total
        FROM receipts
        GROUP BY category
        ORDER BY count DESC
        LIMIT 20
    """)
    
    print(f"\n{'Category':<40} {'Count':>6}  {'Amount':>14}")
    print("-" * 64)
    
    for cat, count, amount in cur.fetchall():
        cat_display = cat or 'NULL'
        amount_str = f"${amount:,.2f}" if amount else "$0.00"
        marker = "✅" if cat not in ('Unknown', 'TRANSFERS', None) else "⚠️"
        print(f"{marker} {cat_display:<37} {count:>6,}  {amount_str:>14}")
        
    # Show top Unknown vendors
    print("\n" + "="*80)
    print("TOP 20 'UNKNOWN' CATEGORY VENDORS")
    print("="*80)
    
    cur.execute("""
        SELECT vendor_name, COUNT(*), SUM(gross_amount)
        FROM receipts
        WHERE category = 'Unknown'
        GROUP BY vendor_name
        ORDER BY COUNT(*) DESC
        LIMIT 20
    """)
    
    print(f"\n{'Vendor':<50} {'Count':>6}  {'Amount':>12}")
    print("-" * 72)
    
    for vendor, count, amount in cur.fetchall():
        vendor_display = (vendor or 'NULL')[:50]
        amount_str = f"${amount:,.2f}" if amount else "$0.00"
        print(f"{vendor_display:<50} {count:>6,}  {amount_str:>12}")
    
    response = input("\n✋ COMMIT these changes? (yes/no): ").strip().lower()
    
    if response == 'yes':
        conn.commit()
        print("\n✅ Changes COMMITTED")
    else:
        conn.rollback()
        print("\n❌ Changes ROLLED BACK")
        
except Exception as e:
    conn.rollback()
    print(f"\n❌ ERROR: {e}")
    raise
    
finally:
    cur.close()
    conn.close()
