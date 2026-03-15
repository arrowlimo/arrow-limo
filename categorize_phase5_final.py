"""
PHASE 5: Final Cleanup - Last Clear Patterns
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
print("PHASE 5: FINAL CLEANUP - LAST CLEAR PATTERNS")
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
    
    # 1. More driver/employee expenses
    cur.execute("""
        UPDATE receipts
        SET category = 'Driver Expense', updated_at = NOW()
        WHERE (category IN ('None', 'Unknown', 'BANKING', 'TRANSFERS', 'NULL') OR category IS NULL)
          AND (vendor_name ILIKE '%EMAIL TRANSFER - MUNDY%'
               OR vendor_name ILIKE '%EMAIL TRANSFER - PAT PERRIER%'
               OR vendor_name ILIKE '%EMAIL TRANSFER - GLENN BARKER%'
               OR vendor_name ILIKE '%EMAIL TRANSFER - DAVID RICHARD%'
               OR vendor_name ILIKE '%EMAIL TRANSFER - PERRIER%'
               OR vendor_name ILIKE '%EMAIL TRANSFER - BARKER%')
    """)
    more_email = cur.rowcount
    print(f"1. More Driver/Employee Expenses: {more_email:,} receipts")
    
    # 2. Vehicle financing (RIFCO, ASI FINANCE)
    cur.execute("""
        UPDATE receipts
        SET category = 'Vehicle Financing', updated_at = NOW()
        WHERE (category IN ('None', 'Unknown', 'BANKING', 'TRANSFERS', 'NULL') OR category IS NULL)
          AND (vendor_name ILIKE '%RIFCO%'
               OR vendor_name ILIKE '%ASI FINANCE%'
               OR vendor_name ILIKE '%ASI FINANCI%')
    """)
    finance = cur.rowcount
    print(f"2. Vehicle Financing (RIFCO, ASI): {finance:,} receipts")
    
    # 3. Telecommunications (TELUS that was missed)
    cur.execute("""
        UPDATE receipts
        SET category = 'Telecommunications', updated_at = NOW()
        WHERE (category IN ('None', 'Unknown', 'BANKING', 'TRANSFERS', 'NULL') OR category IS NULL)
          AND vendor_name ILIKE '%TELUS%'
    """)
    telus = cur.rowcount
    print(f"3. Telecommunications (TELUS): {telus:,} receipts")
    
    # 4. More groceries/client service
    cur.execute("""
        UPDATE receipts
        SET category = 'Client Beverages', updated_at = NOW()
        WHERE (category IN ('None', 'Unknown', 'BANKING', 'TRANSFERS', 'NULL') OR category IS NULL)
          AND (vendor_name ILIKE '%FRESHCO%'
               OR vendor_name ILIKE '%SAFEWAY%'
               OR vendor_name ILIKE '%WALMART%'
               OR vendor_name ILIKE '%SHOPPERS DRUG%'
               OR vendor_name ILIKE '%REAL CDN%WHOLE%')
    """)
    retail = cur.rowcount
    print(f"4. More Groceries/Retail (Client): {retail:,} receipts")
    
    # 5. Government fees (City of Red Deer)
    cur.execute("""
        UPDATE receipts
        SET category = 'Government Fees', updated_at = NOW()
        WHERE (category IN ('None', 'Unknown', 'BANKING', 'TRANSFERS', 'NULL') OR category IS NULL)
          AND (vendor_name ILIKE '%CITY OF RED DEER%'
               OR vendor_name ILIKE '%MUNICIPALITY%')
    """)
    government = cur.rowcount
    print(f"5. Government Fees (City): {government:,} receipts")
    
    # 6. Building/Maintenance supplies (Home Depot)
    cur.execute("""
        UPDATE receipts
        SET category = 'Supplies', updated_at = NOW()
        WHERE (category IN ('None', 'Unknown', 'BANKING', 'TRANSFERS', 'NULL') OR category IS NULL)
          AND vendor_name ILIKE '%HOME DEPOT%'
    """)
    supplies = cur.rowcount
    print(f"6. Supplies (Home Depot): {supplies:,} receipts")
    
    # 7. More bank fees
    cur.execute("""
        UPDATE receipts
        SET category = 'Bank Fees', updated_at = NOW()
        WHERE (category IN ('None', 'Unknown', 'BANKING', 'TRANSFERS', 'NULL') OR category IS NULL)
          AND (vendor_name ILIKE '%OVERDRAFT INTEREST%'
               OR vendor_name ILIKE '%ACCOUNT FEE%'
               OR vendor_name ILIKE '%MONTHLY FEE%')
    """)
    more_bank_fees = cur.rowcount
    print(f"7. More Bank Fees: {more_bank_fees:,} receipts")
    
    # 8. Client entertainment (Cineplex, etc.)
    cur.execute("""
        UPDATE receipts
        SET category = 'Client Entertainment', updated_at = NOW()
        WHERE (category IN ('None', 'Unknown', 'BANKING', 'TRANSFERS', 'NULL') OR category IS NULL)
          AND (vendor_name ILIKE '%CINEPLEX%'
               OR vendor_name ILIKE '%THEATRE%'
               OR vendor_name ILIKE '%MOVIE%')
    """)
    entertainment = cur.rowcount
    print(f"8. Client Entertainment (Cineplex): {entertainment:,} receipts")
    
    # 9. Business supplies/equipment (LFG BUSINESS PAD, CENTEX)
    cur.execute("""
        UPDATE receipts
        SET category = 'Office Supplies', updated_at = NOW()
        WHERE (category IN ('None', 'Unknown', 'BANKING', 'TRANSFERS', 'NULL') OR category IS NULL)
          AND (vendor_name ILIKE '%LFG BUSINESS%'
               OR vendor_name ILIKE '%BUSINESS PAD%'
               OR vendor_name ILIKE '%CENTEX%')
    """)
    business = cur.rowcount
    print(f"9. Business Supplies (LFG, CENTEX): {business:,} receipts")
    
    total_categorized = more_email + finance + telus + retail + government + supplies + more_bank_fees + entertainment + business
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
    cur.execute("SELECT COUNT(*), SUM(gross_amount) FROM receipts")
    total_receipts, total_amount = cur.fetchone()
    categorization_rate = ((total_receipts - after_count) / total_receipts) * 100
    
    print(f"\n📊 Overall categorization rate: {categorization_rate:.1f}% ({total_receipts - after_count:,} / {total_receipts:,})")
    print(f"📊 Total receipts value: ${total_amount:,.2f}")
    print(f"📊 Uncategorized value: ${after_amount:,.2f} ({after_amount/total_amount*100:.1f}% of total)")
    
    # Category breakdown
    print("\n" + "="*80)
    print("CATEGORY SUMMARY")
    print("="*80)
    
    cur.execute("""
        SELECT 
            CASE 
                WHEN category IN ('None', 'Unknown', 'BANKING', 'TRANSFERS', 'NULL') OR category IS NULL 
                THEN '⚠️  UNCATEGORIZED'
                ELSE '✅ ' || category
            END as cat_display,
            COUNT(*) as count,
            SUM(gross_amount) as total
        FROM receipts
        GROUP BY 
            CASE 
                WHEN category IN ('None', 'Unknown', 'BANKING', 'TRANSFERS', 'NULL') OR category IS NULL 
                THEN '⚠️  UNCATEGORIZED'
                ELSE '✅ ' || category
            END
        ORDER BY count DESC
        LIMIT 15
    """)
    
    print(f"\n{'Category':<45} {'Count':>6}  {'Amount':>14}")
    print("-" * 69)
    
    for cat, count, amount in cur.fetchall():
        amount_str = f"${amount:,.2f}" if amount else "$0.00"
        print(f"{cat:<45} {count:>6,}  {amount_str:>14}")
    
    # Show top remaining vendors
    print("\n" + "="*80)
    print("TOP 15 REMAINING UNCATEGORIZED VENDORS")
    print("="*80)
    
    cur.execute("""
        SELECT vendor_name, COUNT(*), SUM(gross_amount)
        FROM receipts
        WHERE category IN ('None', 'Unknown', 'BANKING', 'TRANSFERS', 'NULL') OR category IS NULL
        GROUP BY vendor_name
        ORDER BY COUNT(*) DESC
        LIMIT 15
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
