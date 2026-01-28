"""
Verify Personal Expense Tracking in Receipts
- Show receipts with owner_personal_amount > 0
- Check airport parking categorization
- Verify business/personal splits are tracked
"""

import psycopg2
import os

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

def verify_personal_tracking():
    """Verify personal expense tracking"""
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cur = conn.cursor()
    
    print("=" * 100)
    print("PERSONAL EXPENSE TRACKING VERIFICATION")
    print("=" * 100)
    
    # 1. Check receipts with personal amounts
    print("\n📊 RECEIPTS WITH PERSONAL EXPENSE TRACKING:")
    cur.execute("""
        SELECT 
            EXTRACT(YEAR FROM receipt_date) as year,
            COUNT(*) as count,
            SUM(gross_amount) as total_gross,
            SUM(owner_personal_amount) as total_personal,
            SUM(gross_amount - COALESCE(owner_personal_amount, 0)) as total_business
        FROM receipts
        WHERE owner_personal_amount > 0
        GROUP BY EXTRACT(YEAR FROM receipt_date)
        ORDER BY year
    """)
    
    personal_summary = cur.fetchall()
    grand_total_personal = 0
    
    if personal_summary:
        print("\nYear | Receipts | Gross Amount | Personal | Business")
        print("-" * 70)
        for year, count, gross, personal, business in personal_summary:
            print(f"{int(year)} | {count:>8} | ${gross:>11,.2f} | ${personal:>9,.2f} | ${business:>11,.2f}")
            grand_total_personal += personal
        
        print(f"\nTotal Personal Expenses Tracked: ${grand_total_personal:,.2f}")
    else:
        print("⚠️  No receipts found with owner_personal_amount > 0")
    
    # 2. Airport parking (Calgary & Edmonton)
    print("\n" + "=" * 100)
    print("✈️  AIRPORT PARKING FEES")
    print("=" * 100)
    
    cur.execute("""
        SELECT 
            vendor_name,
            COUNT(*) as count,
            SUM(gross_amount) as total,
            gl_account_code,
            gl_account_name
        FROM receipts
        WHERE vendor_name ~* 'airport.*authority|calgary.*airport|edmonton.*airport'
        GROUP BY vendor_name, gl_account_code, gl_account_name
        ORDER BY vendor_name, count DESC
    """)
    
    airport = cur.fetchall()
    if airport:
        for vendor, count, total, code, name in airport:
            print(f"\n{vendor}")
            print(f"   {count} receipts, ${total:,.2f}")
            print(f"   GL: {code or 'NULL'} — {name or 'No Name'}")
    else:
        print("No airport authority receipts found")
    
    # 3. Tim Hortons (mixed business/personal)
    print("\n" + "=" * 100)
    print("☕ TIM HORTONS PURCHASES (Business vs Personal)")
    print("=" * 100)
    
    cur.execute("""
        SELECT 
            EXTRACT(YEAR FROM receipt_date) as year,
            COUNT(*) as total_receipts,
            SUM(gross_amount) as total_amount,
            COUNT(CASE WHEN owner_personal_amount > 0 THEN 1 END) as personal_count,
            SUM(COALESCE(owner_personal_amount, 0)) as personal_amount,
            SUM(gross_amount - COALESCE(owner_personal_amount, 0)) as business_amount
        FROM receipts
        WHERE vendor_name ~* 'tim.*horton'
        GROUP BY EXTRACT(YEAR FROM receipt_date)
        ORDER BY year
    """)
    
    tims = cur.fetchall()
    if tims:
        print("\nYear | Total Receipts | Total $ | Personal Receipts | Personal $ | Business $")
        print("-" * 90)
        for year, total_rct, total_amt, pers_cnt, pers_amt, bus_amt in tims:
            print(f"{int(year)} | {total_rct:>14} | ${total_amt:>8,.2f} | {pers_cnt:>17} | ${pers_amt:>10,.2f} | ${bus_amt:>10,.2f}")
    else:
        print("No Tim Hortons receipts found")
    
    # 4. Driver meal reimbursements
    print("\n" + "=" * 100)
    print("🍔 DRIVER MEAL REIMBURSEMENTS (Out of town)")
    print("=" * 100)
    
    cur.execute("""
        SELECT 
            EXTRACT(YEAR FROM receipt_date) as year,
            COUNT(*) as count,
            SUM(gross_amount) as total
        FROM receipts
        WHERE is_driver_reimbursement = true
           OR description ~* 'driver.*meal|out.*town.*meal|meal.*reimburse'
        GROUP BY EXTRACT(YEAR FROM receipt_date)
        ORDER BY year
    """)
    
    driver_meals = cur.fetchall()
    if driver_meals:
        print("\nYear | Receipts | Amount")
        print("-" * 40)
        for year, count, total in driver_meals:
            print(f"{int(year)} | {count:>8} | ${total:>10,.2f}")
    else:
        print("ℹ️  No receipts flagged as driver reimbursements")
        print("   (Check if is_driver_reimbursement field is being used)")
    
    # 5. Sample personal expense receipts
    print("\n" + "=" * 100)
    print("📋 SAMPLE PERSONAL EXPENSE RECEIPTS (2019-2024)")
    print("=" * 100)
    
    cur.execute("""
        SELECT 
            receipt_date,
            vendor_name,
            gross_amount,
            owner_personal_amount,
            (gross_amount - owner_personal_amount) as business_amount,
            description
        FROM receipts
        WHERE owner_personal_amount > 0
        ORDER BY receipt_date DESC
        LIMIT 30
    """)
    
    samples = cur.fetchall()
    if samples:
        print("\nDate       | Vendor                          | Gross    | Personal | Business | Description")
        print("-" * 120)
        for date, vendor, gross, personal, business, desc in samples:
            vendor_str = (vendor or 'Unknown')[:30]
            desc_str = (desc or '')[:40]
            print(f"{date} | {vendor_str:30s} | ${gross:>7,.2f} | ${personal:>8,.2f} | ${business:>8,.2f} | {desc_str}")
    
    # 6. Recommendations
    print("\n" + "=" * 100)
    print("💡 RECOMMENDATIONS")
    print("=" * 100)
    
    print("\n✅ KEEP CURRENT SYSTEM:")
    print("   • Personal expense tracking via owner_personal_amount")
    print("   • Diverse GL codes for proper categorization")
    print("   • Split business/personal for tax reporting")
    
    print("\n⚠️  ENSURE CONSISTENT USE OF:")
    print("   • owner_personal_amount field for owner's personal expenses")
    print("   • is_driver_reimbursement flag for driver meals")
    print("   • Proper GL codes for different expense types")
    
    print("\n📌 SUGGESTED GL CODES:")
    print("   • Airport parking: 5220 (Vehicle Repairs & Maintenance) or create 5225 (Parking Fees)")
    print("   • Driver meals: 5700 (Travel and Entertainment)")
    print("   • Client amenities: 5116 (Client Amenities - Food, Coffee, Supplies)")
    print("   • Client beverages: 4115 (Client Beverage Service Charges)")
    
    cur.close()
    conn.close()
    
    print("\n" + "=" * 100)


if __name__ == "__main__":
    verify_personal_tracking()
