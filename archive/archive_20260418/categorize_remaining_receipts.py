"""
Categorize Remaining Uncategorized Receipts
Focus on EMAIL TRANSFER, HEFFNER, and other patterns
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
print("PHASE 3: CATEGORIZE REMAINING RECEIPTS")
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
    
    # 1. Employee reimbursements - Mike Woodrow (rent)
    cur.execute("""
        UPDATE receipts
        SET category = 'Rent', updated_at = NOW()
        WHERE (category IN ('None', 'Unknown', 'BANKING', 'TRANSFERS') OR category IS NULL)
          AND vendor_name ILIKE '%MIKE WOODROW%'
    """)
    mike_woodrow = cur.rowcount
    print(f"1. Mike Woodrow (Rent): {mike_woodrow:,} receipts")
    
    # 2. Driver reimbursements
    cur.execute("""
        UPDATE receipts
        SET category = 'Driver Expense', updated_at = NOW()
        WHERE (category IN ('None', 'Unknown', 'BANKING', 'TRANSFERS') OR category IS NULL)
          AND (vendor_name ILIKE '%JOHN MCLEAN%'
               OR vendor_name ILIKE '%JEANNIE SHILLINGTON%'
               OR vendor_name ILIKE '%PAUL MANSELL%')
    """)
    driver_reimburse = cur.rowcount
    print(f"2. Driver Reimbursements: {driver_reimburse:,} receipts")
    
    # 3. Other employee reimbursements (generic EMAIL TRANSFER)
    cur.execute("""
        UPDATE receipts
        SET category = 'Driver Expense', updated_at = NOW()
        WHERE (category IN ('None', 'Unknown', 'BANKING', 'TRANSFERS') OR category IS NULL)
          AND (vendor_name ILIKE 'EMAIL TRANSFER - PEACOCK'
               OR vendor_name ILIKE 'EMAIL TRANSFER - MICHAEL RICHARD'
               OR vendor_name ILIKE 'EMAIL TRANSFER - TABATHA FOULSTON'
               OR vendor_name ILIKE 'EMAIL TRANSFER - RICHARD GURSKY'
               OR vendor_name ILIKE 'EMAIL TRANSFER - ELIZABETH BULIC'
               OR vendor_name ILIKE 'EMAIL TRANSFER - SEAN THOMAS'
               OR vendor_name ILIKE 'EMAIL TRANSFER - MATTHEW DONAT RICHARD')
    """)
    other_drivers = cur.rowcount
    print(f"3. Other Driver Expenses: {other_drivers:,} receipts")
    
    # 4. Vehicle Financing - HEFFNER
    cur.execute("""
        UPDATE receipts
        SET category = 'Vehicle Financing', updated_at = NOW()
        WHERE (category IN ('None', 'Unknown', 'BANKING', 'TRANSFERS') OR category IS NULL)
          AND vendor_name ILIKE '%HEFFNER%'
    """)
    heffner = cur.rowcount
    print(f"4. HEFFNER (Vehicle Financing): {heffner:,} receipts")
    
    # 5. Vehicle Lease - LEASE FINANCE
    cur.execute("""
        UPDATE receipts
        SET category = 'Vehicle Lease', updated_at = NOW()
        WHERE (category IN ('None', 'Unknown', 'BANKING', 'TRANSFERS') OR category IS NULL)
          AND (vendor_name ILIKE '%LEASE FINANCE%'
               OR vendor_name ILIKE '%JACK CARTER%')
    """)
    lease = cur.rowcount
    print(f"5. Vehicle Lease: {lease:,} receipts")
    
    # 6. Fuel purchases (from banking descriptions)
    cur.execute("""
        UPDATE receipts
        SET category = 'Fuel', updated_at = NOW()
        WHERE (category IN ('None', 'Unknown', 'BANKING', 'TRANSFERS') OR category IS NULL)
          AND (vendor_name ILIKE '%FUEL PURCHASE%'
               OR vendor_name ILIKE '%FGP50394%'
               OR vendor_name ILIKE '%RUN''N%'
               OR vendor_name ILIKE '%PETRO%'
               OR vendor_name ILIKE '%CO-OP%'
               OR vendor_name ILIKE '%COOP%GAETZ%')
    """)
    fuel = cur.rowcount
    print(f"6. Fuel: {fuel:,} receipts")
    
    # 7. Groceries/Food (retail purchases for client service)
    cur.execute("""
UPDATE receipts
        SET category = 'Client Beverages', updated_at = NOW()
        WHERE (category IN ('None', 'Unknown', 'BANKING', 'TRANSFERS') OR category IS NULL)
          AND (vendor_name ILIKE '%SAVE ON FOODS%'
               OR vendor_name ILIKE '%REAL CDN SUPERS%'
               OR vendor_name ILIKE '%FOOD PURCHASE%'
               OR vendor_name ILIKE '%SUPERSTORE%')
    """)
    groceries = cur.rowcount
    print(f"7. Groceries (Client Service): {groceries:,} receipts")
    
    # 8. Generic EMAIL TRANSFER (uncategorized employee expenses)
    cur.execute("""
        UPDATE receipts
        SET category = 'Driver Expense', updated_at = NOW()
        WHERE (category IN ('None', 'Unknown', 'BANKING', 'TRANSFERS') OR category IS NULL)
          AND vendor_name = 'EMAIL TRANSFER'
          AND gross_amount < 1000
    """)
    generic_email = cur.rowcount
    print(f"8. Generic EMAIL TRANSFER (<$1000): {generic_email:,} receipts")
    
    # 9. Bank service fees
    cur.execute("""
        UPDATE receipts
        SET category = 'Bank Fees', updated_at = NOW()
        WHERE (category IN ('None', 'Unknown', 'BANKING', 'TRANSFERS') OR category IS NULL)
          AND (vendor_name ILIKE '%BANK SERVICE%'
               OR vendor_name ILIKE '%SERVICE FEE%')
    """)
    bank_fee = cur.rowcount
    print(f"9. Bank Service Fees: {bank_fee:,} receipts")
    
    total_categorized = mike_woodrow + driver_reimburse + other_drivers + heffner + lease + fuel + groceries + generic_email + bank_fee
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
