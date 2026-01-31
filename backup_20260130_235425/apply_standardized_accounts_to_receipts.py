"""
Apply Standardized GL Accounts to Receipts
Updates receipts with new GL account codes based on mappings
Adds sub-categorization for generic 'Business expense' and 'OTHER_EXPENSE' items
"""

import psycopg2
from datetime import datetime

# Connect to database
conn = psycopg2.connect(
    dbname='almsdata',
    user='postgres',
    password='***REDACTED***',
    host='localhost'
)

# Vendor-based sub-categorization for generic categories
# GL codes that should be GST exempt (financial services, transfers, prepaid card loads)
GST_EXEMPT_GL_CODES = {
    '6100',  # Bank Charges & Interest
    '6101',  # Interest & Late Charges
    '5450',  # Payment Processing Fees (financial services)
    '1135',  # Prepaid Visa Cards (asset; loads are non-taxable)
    '1099',  # Inter-Account Clearing (internal transfers)
}

VENDOR_SUBCATEGORY_RULES = {
    # Fuel vendors → 5110 (Vehicle Fuel)
    'fuel': {
        'patterns': ['FAS GAS', 'PETRO', 'SHELL', 'CO-OP', 'CHEVRON', 'ESSO', 'HUSKY', 'RUN', 'EMPTY', 'GAS', 'FUEL'],
        'account': '5110',
        'subcategory': 'Vehicle Fuel'
    },
    
    # Food/Entertainment → 5710 (Meals) or 5730 (Client Entertainment)
    'food': {
        'patterns': ['LIQUOR', 'RESTAURANT', 'TIM HORTONS', 'MCDONALDS', 'SUBWAY', 'STARBUCKS', 'COFFEE', 'PIZZA', 'FOOD'],
        'account': '5710',
        'subcategory': 'Meals and Entertainment'
    },
    
    # Telecom → 5630 (Mobile Phones) or 5620 (Internet)
    'telecom': {
        'patterns': ['TELUS', 'ROGERS', 'BELL', 'SHAW', 'FIDO', 'VIRGIN', 'KOODO'],
        'account': '5630',
        'subcategory': 'Telecommunications'
    },
    
    # Office supplies → 5510
    'office': {
        'patterns': ['STAPLES', 'OFFICE', 'DEPOT', 'PAPER', 'PRINTER', 'INK', 'SUPPLIES'],
        'account': '5510',
        'subcategory': 'Office Supplies'
    },
    
    # Maintenance → 5210
    'maintenance': {
        'patterns': ['REPAIR', 'MAINTENANCE', 'AUTO', 'TIRE', 'OIL CHANGE', 'CARWASH', 'WASH'],
        'account': '5210',
        'subcategory': 'Vehicle Maintenance'
    },
    
    # Parking → 5740
    'parking': {
        'patterns': ['PARK', 'IMPARK', 'LOT', 'METER'],
        'account': '5740',
        'subcategory': 'Parking and Tolls'
    },
    
    # Professional fees → 5810/5820/5830
    'professional': {
        'patterns': ['ACCOUNTING', 'LEGAL', 'LAWYER', 'CONSULT', 'CPA'],
        'account': '5810',
        'subcategory': 'Professional Fees'
    },
    
    # Bank/Financial → 5410
    'financial': {
        'patterns': ['BANK', 'MONEY MART', 'WESTERN UNION', 'PAYPAL', 'SQUARE'],
        'account': '5450',
        'subcategory': 'Payment Processing Fees'
    },
    
    # Insurance → 5310
    'insurance': {
        'patterns': ['INSURANCE', 'SGI', 'ICBC', 'MPI'],
        'account': '5310',
        'subcategory': 'Vehicle Insurance'
    },
}

def add_gl_account_column():
    """Add new column for standardized GL account code"""
    cur = conn.cursor()
    
    # Check if column exists
    cur.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'receipts' 
        AND column_name = 'gl_account_code'
    """)
    
    if not cur.fetchone():
        cur.execute("""
            ALTER TABLE receipts 
            ADD COLUMN gl_account_code VARCHAR(10),
            ADD COLUMN gl_account_name VARCHAR(200),
            ADD COLUMN gl_subcategory VARCHAR(200),
            ADD COLUMN auto_categorized BOOLEAN DEFAULT false
        """)
        conn.commit()
        print("✓ Added GL account columns to receipts table")
    else:
        print("✓ GL account columns already exist")

def ensure_gst_exempt_column():
    """Ensure receipts table has gst_exempt column (BOOLEAN)."""
    cur = conn.cursor()
    cur.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'receipts' 
        AND column_name = 'gst_exempt'
    """)
    if not cur.fetchone():
        print("Adding gst_exempt column to receipts table...")
        cur.execute("""
            ALTER TABLE receipts 
            ADD COLUMN gst_exempt BOOLEAN DEFAULT FALSE
        """)
        conn.commit()
        print("✓ Added gst_exempt column (defaults to FALSE)")
    else:
        print("✓ gst_exempt column already exists")

def apply_direct_mappings():
    """Apply mappings where expense_account matches exactly"""
    cur = conn.cursor()
    
    cur.execute("""
        UPDATE receipts r
        SET 
            gl_account_code = cm.new_account_code,
            gl_account_name = coa.account_name,
            auto_categorized = true
        FROM category_mappings cm
        JOIN chart_of_accounts coa ON cm.new_account_code = coa.account_code
        WHERE r.expense_account = cm.old_category
        AND r.expense_account NOT IN ('Business expense', 'OTHER_EXPENSE')
        AND r.gl_account_code IS NULL
    """)
    
    count = cur.rowcount
    conn.commit()
    print(f"✓ Applied direct mappings to {count:,} receipts")
    return count

def apply_vendor_based_categorization():
    """Categorize 'Business expense' and 'OTHER_EXPENSE' based on vendor patterns"""
    cur = conn.cursor()
    
    total_categorized = 0
    
    for rule_name, rule in VENDOR_SUBCATEGORY_RULES.items():
        patterns = rule['patterns']
        account = rule['account']
        subcategory = rule['subcategory']
        
        # Build SQL pattern matching
        conditions = ' OR '.join([f"UPPER(r.vendor_name) LIKE UPPER('%{p}%')" for p in patterns])
        
        cur.execute(f"""
            UPDATE receipts r
            SET 
                gl_account_code = '{account}',
                gl_account_name = (SELECT account_name FROM chart_of_accounts WHERE account_code = '{account}'),
                gl_subcategory = '{subcategory}',
                auto_categorized = true
            WHERE r.expense_account IN ('Business expense', 'OTHER_EXPENSE')
            AND r.gl_account_code IS NULL
            AND ({conditions})
        """)
        count = cur.rowcount
        total_categorized += count
        
        if count > 0:
            print(f"  - {rule_name}: {count} receipts → {account} ({subcategory})")
    
    conn.commit()
    print(f"✓ Vendor-based categorization: {total_categorized:,} receipts")
    return total_categorized

def apply_money_mart_prepaid_mapping():
    """Map Money Mart prepaid card loads to 1135 (asset, GST-exempt)."""
    cur = conn.cursor()
    patterns = ["PREPAID", "RELOAD", "VISA", "CARD"]
    like_clause = " OR ".join([f"UPPER(r.description) LIKE '%{p}%'" for p in patterns])
    cur.execute(f"""
        UPDATE receipts r
        SET 
            gl_account_code = '1135',
            gl_account_name = (SELECT account_name FROM chart_of_accounts WHERE account_code = '1135'),
            gl_subcategory = 'Asset Transfer',
            auto_categorized = true,
            gst_exempt = TRUE
        WHERE UPPER(r.vendor_name) LIKE '%MONEY MART%'
        AND ({like_clause})
        AND (r.gl_account_code IS NULL OR r.gl_account_code IN ('5850','5450'))
    """)
    count = cur.rowcount
    conn.commit()
    print(f"✓ Money Mart prepaid→1135: {count:,} receipts")
    return count

def apply_gst_exempt_rules():
    """Mark receipts GST-exempt when linked to specific GL codes or financial-service categories."""
    cur = conn.cursor()

    # By GL code whitelist
    cur.execute(
        """
        UPDATE receipts r
        SET gst_exempt = TRUE
        WHERE r.gl_account_code IN %s
        AND COALESCE(r.gst_exempt, FALSE) = FALSE
        """,
        (tuple(GST_EXEMPT_GL_CODES),)
    )
    count_codes = cur.rowcount

    # Defensive: payment processor descriptors without GL yet → mark exempt once mapped
    # (No-op here if gl not set; mapping functions above should set 5450 first.)

    conn.commit()
    print(f"✓ GST-exempt applied by GL code: {count_codes:,} receipts")
    return count_codes

def handle_remaining_generic_expenses():
    """Assign remaining Business expense/OTHER_EXPENSE to 5930 (Miscellaneous)"""
    cur = conn.cursor()
    
    cur.execute("""
        UPDATE receipts r
        SET 
            gl_account_code = '5930',
            gl_account_name = 'Miscellaneous',
            gl_subcategory = 'Uncategorized - Needs Review',
            auto_categorized = false
        WHERE r.expense_account IN ('Business expense', 'OTHER_EXPENSE')
        AND r.gl_account_code IS NULL
    """)
    
    count = cur.rowcount
    conn.commit()
    print(f"⚠ Remaining generic expenses → 5930 (Miscellaneous): {count:,} receipts (manual review needed)")
    return count

def generate_update_report():
    """Generate report on what was updated"""
    cur = conn.cursor()
    
    print("\n" + "="*80)
    print("GL ACCOUNT UPDATE REPORT")
    print("="*80)
    
    # Overall summary
    cur.execute("""
        SELECT 
            COUNT(*) as total,
            COUNT(gl_account_code) as categorized,
            COUNT(*) - COUNT(gl_account_code) as uncategorized
        FROM receipts
    """)
    
    total, categorized, uncategorized = cur.fetchone()
    pct = (categorized / total * 100) if total > 0 else 0
    
    print(f"\nOverall Status:")
    print(f"  Total receipts:      {total:,}")
    print(f"  Categorized:         {categorized:,} ({pct:.1f}%)")
    print(f"  Still uncategorized: {uncategorized:,}")
    
    # By GL account
    print(f"\nReceipts by GL Account:")
    print("-" * 80)
    cur.execute("""
        SELECT 
            r.gl_account_code,
            r.gl_account_name,
            COUNT(*) as count,
            SUM(r.gross_amount) as total_amount,
            SUM(CASE WHEN r.auto_categorized THEN 1 ELSE 0 END) as auto_count,
            SUM(CASE WHEN NOT r.auto_categorized THEN 1 ELSE 0 END) as manual_count
        FROM receipts r
        WHERE r.gl_account_code IS NOT NULL
        GROUP BY r.gl_account_code, r.gl_account_name
        ORDER BY count DESC
    """)
    
    for code, name, count, amount, auto, manual in cur.fetchall():
        marker = "⚠" if manual > 0 else "✓"
        safe_name = name or ""
        safe_amount = amount or 0
        print(f"{marker} {code}: {safe_name:40} {count:6,} receipts  ${safe_amount:>14,.2f}")
        if manual > 0:
            print(f"       → {manual:,} need manual review")

    # GST-exempt summary
    print(f"\nGST Exempt Status:")
    print("-" * 80)
    cur.execute("""
        SELECT 
            COALESCE(gst_exempt, FALSE) AS is_exempt,
            COUNT(*) AS cnt,
            SUM(gross_amount) AS total_amount
        FROM receipts
        GROUP BY COALESCE(gst_exempt, FALSE)
        ORDER BY is_exempt DESC
    """)
    for is_exempt, cnt, total_amount in cur.fetchall():
        label = "GST EXEMPT" if is_exempt else "Taxed/Unknown"
        print(f"✓ {label:15} {cnt:6,} receipts  ${total_amount or 0:>14,.2f}")
    
    # By subcategory
    print(f"\nReceipts by Subcategory:")
    print("-" * 80)
    cur.execute("""
        SELECT 
            r.gl_subcategory,
            COUNT(*) as count,
            SUM(r.gross_amount) as total_amount
        FROM receipts r
        WHERE r.gl_subcategory IS NOT NULL
        GROUP BY r.gl_subcategory
        ORDER BY count DESC
    """)
    
    for subcat, count, amount in cur.fetchall():
        marker = "⚠" if "Uncategorized" in (subcat or "") else "✓"
        print(f"{marker} {subcat:50} {count:6,} receipts  ${amount:>14,.2f}")
    
    # Old expense accounts still without mapping
    print(f"\nOld Expense Accounts Not Yet Mapped:")
    print("-" * 80)
    cur.execute("""
        SELECT 
            r.expense_account,
            COUNT(*) as count,
            SUM(r.gross_amount) as total_amount
        FROM receipts r
        WHERE r.expense_account IS NOT NULL
        AND r.gl_account_code IS NULL
        GROUP BY r.expense_account
        ORDER BY count DESC
    """)
    
    unmapped = cur.fetchall()
    if unmapped:
        for old_acct, count, amount in unmapped:
            print(f"⚠ {old_acct:50} {count:6,} receipts  ${amount:>14,.2f}")
    else:
        print("✓ All expense accounts have been mapped!")

def create_summary_views():
    """Create database views for easy reporting"""
    cur = conn.cursor()
    
    # Drop existing views
    cur.execute("DROP VIEW IF EXISTS receipts_by_gl_account CASCADE")
    cur.execute("DROP VIEW IF EXISTS receipts_by_subcategory CASCADE")
    cur.execute("DROP VIEW IF EXISTS receipts_needing_review CASCADE")
    
    # View 1: Receipts by GL Account
    cur.execute("""
        CREATE VIEW receipts_by_gl_account AS
        SELECT 
            r.gl_account_code,
            r.gl_account_name,
            EXTRACT(YEAR FROM r.receipt_date) as year,
            COUNT(*) as receipt_count,
            SUM(r.gross_amount) as total_amount,
            SUM(CASE WHEN r.auto_categorized THEN 1 ELSE 0 END) as auto_categorized_count
        FROM receipts r
        WHERE r.gl_account_code IS NOT NULL
        GROUP BY r.gl_account_code, r.gl_account_name, EXTRACT(YEAR FROM r.receipt_date)
        ORDER BY year, r.gl_account_code
    """)
    
    # View 2: Receipts by Subcategory
    cur.execute("""
        CREATE VIEW receipts_by_subcategory AS
        SELECT 
            r.gl_account_code,
            r.gl_subcategory,
            EXTRACT(YEAR FROM r.receipt_date) as year,
            COUNT(*) as receipt_count,
            SUM(r.gross_amount) as total_amount
        FROM receipts r
        WHERE r.gl_subcategory IS NOT NULL
        GROUP BY r.gl_account_code, r.gl_subcategory, EXTRACT(YEAR FROM r.receipt_date)
        ORDER BY year, r.gl_account_code, r.gl_subcategory
    """)
    
    # View 3: Receipts needing manual review
    cur.execute("""
        CREATE VIEW receipts_needing_review AS
        SELECT 
            r.receipt_id,
            r.receipt_date,
            r.vendor_name,
            r.gross_amount,
            r.expense_account as old_category,
            r.gl_account_code,
            r.gl_account_name,
            r.gl_subcategory,
            r.description
        FROM receipts r
        WHERE r.auto_categorized = false
        OR r.gl_account_code IS NULL
        OR r.gl_subcategory LIKE '%Uncategorized%'
        ORDER BY r.receipt_date DESC
    """)
    
    conn.commit()
    print("✓ Created summary views for reporting")

def main():
    print("Applying Standardized GL Accounts to Receipts...")
    print("="*80)
    
    add_gl_account_column()
    ensure_gst_exempt_column()
    
    print("\n1. Applying Direct Mappings:")
    direct_count = apply_direct_mappings()
    
    print("\n2. Applying Vendor-Based Categorization:")
    vendor_count = apply_vendor_based_categorization()
    
    print("\n3. Handling Remaining Generic Expenses:")
    remaining = handle_remaining_generic_expenses()

    print("\n4. Money Mart prepaid loads:")
    mm_count = apply_money_mart_prepaid_mapping()
 
    print("\n5. Applying GST-Exempt Rules:")
    exempt_count = apply_gst_exempt_rules()
    create_summary_views()
    
    print("\n" + "="*80)
    print("UPDATE COMPLETE!")
    print("="*80)
    print(f"Direct mappings:       {direct_count:,} receipts")
    print(f"Vendor categorization: {vendor_count:,} receipts")
    print(f"Money Mart prepaid→1135: {mm_count:,} receipts")
    print(f"Need manual review:    {remaining:,} receipts")
    print(f"GST-exempt marked:     {exempt_count:,} receipts")
    print(f"\nTotal updated:         {direct_count + vendor_count + remaining + mm_count:,} receipts")
    print("="*80)
    
    print("\nNext Steps:")
    print("1. Query 'receipts_needing_review' view for manual categorization")
    print("2. Add more vendor patterns to improve auto-categorization")
    print("3. Run reports using 'receipts_by_gl_account' view (2002-2025)")
    print("4. Update payment method categorization for card data receipts")
    
    conn.close()

if __name__ == '__main__':
    main()
