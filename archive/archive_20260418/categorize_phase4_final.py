"""
PHASE 4: Final Categorization Pass
Target remaining clear patterns
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
print("PHASE 4: FINAL CATEGORIZATION PASS")
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
    
    # 1. More driver expenses (EMAIL TRANSFER to specific people)
    cur.execute("""
        UPDATE receipts
        SET category = 'Driver Expense', updated_at = NOW()
        WHERE (category IN ('None', 'Unknown', 'BANKING', 'TRANSFERS', 'NULL') OR category IS NULL)
          AND (vendor_name ILIKE '%EMAIL TRANSFER - BRITT%'
               OR vendor_name ILIKE '%EMAIL TRANSFER - OLSEN%'
               OR vendor_name ILIKE '%EMAIL TRANSFER - SHALENE CASTLE%'
               OR vendor_name ILIKE '%EMAIL TRANSFER - VANESSA THOMAS%'
               OR vendor_name ILIKE '%EMAIL TRANSFER - CASTLE%'
               OR vendor_name ILIKE '%EMAIL TRANSFER - THOMAS%')
    """)
    more_drivers = cur.rowcount
    print(f"1. More Driver Expenses: {more_drivers:,} receipts")
    
    # 2. Larger EMAIL TRANSFER amounts (likely rent/large reimbursements)
    cur.execute("""
        UPDATE receipts
        SET category = 'Driver Expense', updated_at = NOW()
        WHERE (category IN ('None', 'Unknown', 'BANKING', 'TRANSFERS', 'NULL') OR category IS NULL)
          AND vendor_name = 'EMAIL TRANSFER'
          AND gross_amount >= 1000
    """)
    large_email = cur.rowcount
    print(f"2. Large EMAIL TRANSFER (>=$1000): {large_email:,} receipts")
    
    # 3. Bank fees (BANK FEES vendor)
    cur.execute("""
        UPDATE receipts
        SET category = 'Bank Fees', updated_at = NOW()
        WHERE (category IN ('None', 'Unknown', 'BANKING', 'TRANSFERS', 'NULL') OR category IS NULL)
          AND vendor_name ILIKE '%BANK FEE%'
    """)
    bank_fees = cur.rowcount
    print(f"3. Bank Fees: {bank_fees:,} receipts")
    
    # 4. Vehicle maintenance (car wash, auto parts)
    cur.execute("""
        UPDATE receipts
        SET category = 'Vehicle Maintenance', updated_at = NOW()
        WHERE (category IN ('None', 'Unknown', 'BANKING', 'TRANSFERS', 'NULL') OR category IS NULL)
          AND (vendor_name ILIKE '%CAR WASH%'
               OR vendor_name ILIKE '%SUPER CLEAN%'
               OR vendor_name ILIKE '%AUTO PARTS%'
               OR vendor_name ILIKE '%AUTO SERVIC%'
               OR vendor_name ILIKE '%MAINTENANCE%')
    """)
    auto_maint = cur.rowcount
    print(f"4. Vehicle Maintenance: {auto_maint:,} receipts")
    
    # 5. More groceries/client service
    cur.execute("""
        UPDATE receipts
        SET category = 'Client Beverages', updated_at = NOW()
        WHERE (category IN ('None', 'Unknown', 'BANKING', 'TRANSFERS', 'NULL') OR category IS NULL)
          AND (vendor_name ILIKE '%SOBEYS%'
               OR vendor_name ILIKE '%GAETZ FRESH%'
               OR vendor_name ILIKE '%REAL CANADIAN%'
               OR vendor_name ILIKE '%604 - LB 67TH%'
               OR vendor_name ILIKE '%WHOLESALE CLUB%')
    """)
    more_groceries = cur.rowcount
    print(f"5. More Groceries (Client Service): {more_groceries:,} receipts")
    
    # 6. More fuel (Co-op, Taylor)
    cur.execute("""
        UPDATE receipts
        SET category = 'Fuel', updated_at = NOW()
        WHERE (category IN ('None', 'Unknown', 'BANKING', 'TRANSFERS', 'NULL') OR category IS NULL)
          AND (vendor_name ILIKE '%COOP%TAYLOR%'
               OR vendor_name ILIKE '%CA COOP%')
    """)
    more_fuel = cur.rowcount
    print(f"6. More Fuel (Co-op): {more_fuel:,} receipts")
    
    # 7. Insurance (mortgage protection)
    cur.execute("""
        UPDATE receipts
        SET category = 'Insurance', updated_at = NOW()
        WHERE (category IN ('None', 'Unknown', 'BANKING', 'TRANSFERS', 'NULL') OR category IS NULL)
          AND vendor_name ILIKE '%MORTGAGE PROTECT%'
    """)
    insurance = cur.rowcount
    print(f"7. Insurance (Mortgage Protection): {insurance:,} receipts")
    
    # 8. Office/Business (iTunes - likely apps/software)
    cur.execute("""
        UPDATE receipts
        SET category = 'Office Supplies', updated_at = NOW()
        WHERE (category IN ('None', 'Unknown', 'BANKING', 'TRANSFERS', 'NULL') OR category IS NULL)
          AND vendor_name ILIKE '%ITUNES%'
    """)
    itunes = cur.rowcount
    print(f"8. iTunes (Office/Software): {itunes:,} receipts")
    
    total_categorized = more_drivers + large_email + bank_fees + auto_maint + more_groceries + more_fuel + insurance + itunes
    print(f"\n📊 TOTAL CATEGORIZED: {total_categorized:,} receipts")
    
    # Check remaining
    cur.execute("""
        SELECT COUNT(*), SUM(gross_amount)
        FROM receipts
        WHERE category IN ('None', 'Unknown', 'BANKING', 'TRANSFERS', 'NULL') OR category IS NULL
    """)
    
    after_count, after_amount = cur.fetchone()
    improvement = before_count - after_count
    
    print("\n" + "="*80)
    print("RESULTS")
    print("="*80)
    print(f"\nBefore: {before_count:,} uncategorized (${before_amount:,.2f})")
    print(f"After:  {after_count:,} uncategorized (${after_amount:,.2f})")
    print(f"\n✅ Improvement: {improvement:,} receipts categorized")
    
    # Overall categorization rate
    cur.execute("SELECT COUNT(*) FROM receipts")
    total_receipts = cur.fetchone()[0]
    categorization_rate = ((total_receipts - after_count) / total_receipts) * 100
    
    print(f"\n📊 Overall categorization rate: {categorization_rate:.1f}% ({total_receipts - after_count:,} / {total_receipts:,})")
    
    # Show top remaining vendors
    print("\n" + "="*80)
    print("TOP 20 REMAINING UNCATEGORIZED VENDORS")
    print("="*80)
    
    cur.execute("""
        SELECT vendor_name, COUNT(*), SUM(gross_amount)
        FROM receipts
        WHERE category IN ('None', 'Unknown', 'BANKING', 'TRANSFERS', 'NULL') OR category IS NULL
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
