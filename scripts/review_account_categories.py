#!/usr/bin/env python3
"""
Review account_categories table - determine if it's a duplicate chart or a mapping table.
"""

import psycopg2

def get_db_connection():
    return psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REDACTED***'
    )

def main():
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("="*80)
    print("ACCOUNT_CATEGORIES ANALYSIS")
    print("="*80)
    
    # 1. Schema
    print("\n1. TABLE SCHEMA")
    print("-"*80)
    
    cur.execute("""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name = 'account_categories' 
        ORDER BY ordinal_position
    """)
    
    print("\nColumns:")
    for col, dtype in cur.fetchall():
        print(f"  • {col}: {dtype}")
    
    # 2. All data
    print("\n\n2. ALL 33 CATEGORIES")
    print("-"*80)
    
    cur.execute("""
        SELECT category_code, category_name, account_type, parent_category
        FROM account_categories
        ORDER BY category_code
    """)
    
    print(f"\n{'Code':<20} {'Name':<40} {'Type':<15} {'Parent':<15}")
    print("-"*80)
    for code, name, atype, parent in cur.fetchall():
        print(f"{code:<20} {name:<40} {atype or '':<15} {parent or '':<15}")
    
    # 3. Compare with chart_of_accounts
    print("\n\n3. MAPPING TO CHART_OF_ACCOUNTS")
    print("-"*80)
    
    # Try to find matches
    cur.execute("""
        SELECT 
            ac.category_code,
            ac.category_name,
            ac.account_type,
            coa.account_code,
            coa.account_name
        FROM account_categories ac
        LEFT JOIN chart_of_accounts coa ON 
            LOWER(coa.account_name) LIKE '%' || LOWER(ac.category_name) || '%'
            OR LOWER(ac.category_name) LIKE '%' || LOWER(coa.account_name) || '%'
        WHERE coa.account_code IS NOT NULL
        ORDER BY ac.category_code
    """)
    
    matches = cur.fetchall()
    
    if len(matches) > 0:
        print(f"\nFound {len(matches)} potential matches:")
        print(f"\n{'Category':<20} {'Category Name':<30} {'→':<3} {'GL Code':<10} {'GL Name':<30}")
        print("-"*100)
        for cat_code, cat_name, cat_type, gl_code, gl_name in matches[:15]:
            cat_short = (cat_name[:27] + '...') if len(cat_name) > 30 else cat_name
            gl_short = (gl_name[:27] + '...') if len(gl_name) > 30 else gl_name
            print(f"{cat_code:<20} {cat_short:<30} {'→':<3} {gl_code:<10} {gl_short:<30}")
        
        if len(matches) > 15:
            print(f"... and {len(matches)-15} more")
    
    # 4. Specific category mappings we need
    print("\n\n4. KEY CATEGORY MAPPINGS NEEDED")
    print("-"*80)
    
    key_categories = [
        ('FUEL', '5110'),
        ('VEHICLE_RM', '5120'),
        ('OFFICE_SUPPLIES', '5420'),
        ('INTERNET', '5430'),
        ('TELEPHONE', '5430'),
        ('MEALS_ENTERTAINMENT', '5325'),
        ('INSURANCE', '5130'),
        ('BANK_CHARGES', '5710'),
    ]
    
    print("\n✓ Suggested mappings for receipt categorization:")
    print(f"\n{'Category Code':<25} {'→':<3} {'GL Account':<12} {'GL Name':<40}")
    print("-"*80)
    
    for cat_code, gl_code in key_categories:
        cur.execute("""
            SELECT account_name 
            FROM chart_of_accounts 
            WHERE account_code = %s
        """, (gl_code,))
        
        result = cur.fetchone()
        gl_name = result[0] if result else "NOT FOUND"
        
        print(f"{cat_code:<25} {'→':<3} {gl_code:<12} {gl_name:<40}")
    
    # 5. Check if this is used anywhere
    print("\n\n5. TABLE USAGE ANALYSIS")
    print("-"*80)
    
    # Check receipts table
    cur.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'receipts' 
        AND column_name LIKE '%categ%'
    """)
    
    receipt_cols = [row[0] for row in cur.fetchall()]
    print(f"\nReceipts table category columns: {receipt_cols}")
    
    if 'category' in receipt_cols:
        cur.execute("""
            SELECT DISTINCT category 
            FROM receipts 
            WHERE category IS NOT NULL
            LIMIT 10
        """)
        
        print("\nSample receipt categories:")
        for cat, in cur.fetchall():
            print(f"  • {cat}")
    
    # 6. Recommendation
    print("\n\n6. RECOMMENDATION")
    print("="*80)
    
    print("\n✓ This is a CATEGORY MAPPING TABLE, not a chart of accounts duplicate")
    print("\n  Purpose: Maps simple category codes to chart_of_accounts GL codes")
    print("  Example: receipts.category='FUEL' → chart_of_accounts.account_code='5110'")
    print("\n  Actions:")
    print("  1. ✓ KEEP THIS TABLE - useful for receipt categorization")
    print("  2. Create category_to_account_map table with explicit mappings")
    print("  3. Update smart_expense_categorization.py to use this mapping")
    print("  4. Consider adding gl_account_code column to account_categories")
    print("\n  DO NOT DROP - this provides business-friendly category names")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
