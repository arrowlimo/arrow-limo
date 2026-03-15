"""
CRA Audit Report - 2012-2015 Receipt Classification Analysis
Detailed breakdown of Personal, Revenue, and all GL code classifications
"""

import psycopg2
from datetime import datetime

conn = psycopg2.connect(
    dbname="almsdata",
    user="postgres",
    password="ArrowLimousine",
    host="localhost"
)
cur = conn.cursor()

print("="*120)
print("CRA AUDIT REPORT - RECEIPT CLASSIFICATION ANALYSIS (2012-2015)")
print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("="*120)

# ============================================================================
# SECTION 1: PERSONAL EXPENSES & OWNER DRAWS (2012-2015)
# ============================================================================
print("\n" + "="*120)
print("SECTION 1: PERSONAL EXPENSES & OWNER DRAWS (2012-2015)")
print("These are NOT deductible business expenses - they represent owner personal use")
print("="*120)

cur.execute("""
    SELECT 
        r.receipt_date,
        r.vendor_name,
        r.category,
        r.gl_account_code,
        coa.account_name as gl_name,
        r.gross_amount,
        r.description,
        r.payment_method
    FROM receipts r
    LEFT JOIN chart_of_accounts coa ON r.gl_account_code = coa.account_code
    WHERE r.business_personal = 'Personal'
      AND r.receipt_date BETWEEN '2012-01-01' AND '2015-12-31'
    ORDER BY r.receipt_date, r.gross_amount DESC
""")

personal_items = cur.fetchall()

if personal_items:
    print(f"\n{'Date':<12} {'Vendor':<30} {'Category':<25} {'GL':<6} {'Amount':>12} {'Description'[:30]}")
    print("-"*120)
    
    year_total = 0
    current_year = None
    grand_total = 0
    
    for date, vendor, cat, gl, gl_name, amt, desc, method in personal_items:
        if current_year != date.year:
            if current_year is not None:
                print("-"*120)
                print(f"{'YEAR ' + str(current_year) + ' TOTAL:':<98} ${year_total:>16,.2f}")
                print()
            current_year = date.year
            year_total = 0
            print(f"\n*** {current_year} ***")
        
        desc_short = (desc or '')[:30]
        print(f"{str(date):<12} {(vendor or '')[:30]:<30} {(cat or '')[:25]:<25} {gl or '':<6} ${amt:>11,.2f} {desc_short}")
        year_total += amt
        grand_total += amt
    
    if current_year:
        print("-"*120)
        print(f"{'YEAR ' + str(current_year) + ' TOTAL:':<98} ${year_total:>16,.2f}")
    
    print("="*120)
    print(f"{'TOTAL PERSONAL EXPENSES (2012-2015):':<98} ${grand_total:>16,.2f}")
    print(f"Count: {len(personal_items)} receipts")
    print("="*120)
else:
    print("\n[OK] No personal expenses found for 2012-2015")

# ============================================================================
# SECTION 2: REVENUE/INCOME ITEMS (Should NOT be in expenses)
# ============================================================================
print("\n" + "="*120)
print("SECTION 2: REVENUE/INCOME ITEMS MARKED AS 'REVENUE_NOT_EXPENSE'")
print("These represent money RECEIVED (charter revenue, customer payments)")
print("CRA AUDIT FINDING: These must be EXCLUDED from business expense deductions")
print("="*120)

cur.execute("""
    SELECT 
        r.receipt_date,
        r.vendor_name,
        r.category,
        r.gl_account_code,
        coa.account_name as gl_name,
        r.gross_amount,
        r.description,
        bt.credit_amount as credit_from_bank
    FROM receipts r
    LEFT JOIN chart_of_accounts coa ON r.gl_account_code = coa.account_code
    LEFT JOIN banking_transactions bt ON r.banking_transaction_id = bt.transaction_id
    WHERE r.business_personal = 'REVENUE_NOT_EXPENSE'
    ORDER BY r.receipt_date DESC
""")

revenue_items = cur.fetchall()

if revenue_items:
    print(f"\n{'Date':<12} {'Vendor':<30} {'Category':<20} {'GL':<6} {'Receipt Amt':>12} {'Bank Credit':>12} {'Description'[:20]}")
    print("-"*120)
    
    total_revenue = 0
    for date, vendor, cat, gl, gl_name, amt, desc, credit in revenue_items:
        desc_short = (desc or '')[:20]
        credit_str = f"${credit:>11,.2f}" if credit else "N/A"
        print(f"{str(date):<12} {(vendor or '')[:30]:<30} {(cat or '')[:20]:<20} {gl or '':<6} ${amt:>11,.2f} {credit_str:>12} {desc_short}")
        total_revenue += amt
    
    print("="*120)
    print(f"{'TOTAL REVENUE INCORRECTLY IN RECEIPTS TABLE:':<88} ${total_revenue:>16,.2f}")
    print(f"Count: {len(revenue_items)} receipts")
    print("\n[WARNING] AUDIT FINDING: These items INCREASE taxable income, not decrease it.")
    print("          They should be tracked in revenue system (charter_charges table), not expenses.")
    print("="*120)
else:
    print("\n[OK] No revenue items found in receipts table")

# Continue with remaining sections...
print("\n" + "="*120)
print("SECTION 3: COMPLETE GL CODE BREAKDOWN (2012-2015)")
print("All receipts grouped by GL code with totals")
print("="*120)

cur.execute("""
    SELECT 
        COALESCE(r.gl_account_code, 'NO GL CODE') as gl_code,
        COALESCE(coa.account_name, 'Unknown') as gl_name,
        COALESCE(coa.account_type, 'Uncategorized') as gl_type,
        r.business_personal,
        COUNT(*) as count,
        SUM(r.gross_amount) as total
    FROM receipts r
    LEFT JOIN chart_of_accounts coa ON r.gl_account_code = coa.account_code
    WHERE r.receipt_date BETWEEN '2012-01-01' AND '2015-12-31'
    GROUP BY r.gl_account_code, coa.account_name, coa.account_type, r.business_personal
    ORDER BY r.gl_account_code, r.business_personal
""")

gl_breakdown = cur.fetchall()

if gl_breakdown:
    current_gl = None
    gl_total = 0
    grand_total = 0
    grand_count = 0
    
    print(f"\n{'GL Code':<10} {'Account Name':<40} {'Type':<15} {'Classification':<20} {'Count':>8} {'Amount':>15}")
    print("-"*120)
    
    for gl, name, gl_type, biz_class, count, amount in gl_breakdown:
        if current_gl != gl:
            if current_gl is not None:
                print("-"*120)
                print(f"{'GL ' + current_gl + ' SUBTOTAL:':<89} {gl_count:>8,} ${gl_total:>14,.2f}")
                print()
            current_gl = gl
            gl_total = 0
            gl_count = 0
        
        print(f"{gl:<10} {name[:40]:<40} {gl_type[:15]:<15} {(biz_class or 'NULL')[:20]:<20} {count:>8,} ${amount:>14,.2f}")
        gl_total += amount
        gl_count += count
        grand_total += amount
        grand_count += count
    
    if current_gl:
        print("-"*120)
        print(f"{'GL ' + current_gl + ' SUBTOTAL:':<89} {gl_count:>8,} ${gl_total:>14,.2f}")
    
    print("="*120)
    print(f"{'GRAND TOTAL (2012-2015):':<89} {grand_count:>8,} ${grand_total:>14,.2f}")
    print("="*120)

print("\n" + "="*120)
print("END OF AUDIT REPORT - See output file for complete details")
print("="*120)

cur.close()
conn.close()
