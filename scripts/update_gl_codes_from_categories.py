#!/usr/bin/env python3
"""
Create comprehensive GL code mapping for all receipt categories.
Then update receipts.gl_account_code based on category.
"""

import psycopg2

DB_CONFIG = {
    'host': 'localhost',
    'database': 'almsdata',
    'user': 'postgres',
    'password': '***REMOVED***'
}

# Comprehensive category → GL code mapping
CATEGORY_GL_MAPPING = {
    # Banking & Transfers (use existing GL where already set)
    'BANKING': '1010',  # Cash - Checking
    'TRANSFERS': '9000',  # Internal Transfers  
    'internal_transfer': '9000',
    'Cheque': '1010',
    'Cash Withdrawal': '1030',  # Petty Cash
    'atm withdrawal': '1030',
    'petty_cash': '1030',
    'Prepaid Card Load': '1135',  # Prepaid Assets
    
    # Revenue
    'Income - Card Payments': '4100',  # Charter Revenue
    'DEPOSITS': '4110',  # Deposits
    'Branch Transaction Revenue': '4130',
    'Internet Banking Revenue': '4120',
    '6000 - Advertising': '6700',  # Move to proper GL
    
    # Vehicle/Fleet Expenses (5000-5999)
    'Fuel': '5110',
    'FUEL': '5110',
    'fuel': '5110',
    'Gas': '5110',
    'Diesel': '5110',
    'Vehicle Maintenance': '5120',
    'maintenance': '5120',
    'Vehicle Repairs': '5130',
    'Vehicle Rental/Maintenance': '5140',  # Rental
    'Vehicle Rental': '5140',
    'Vehicle Insurance': '5200',
    'Insurance - Vehicle Liability': '5200',
    'insurance': '5200',  # Assume vehicle insurance
    'Vehicle Registration': '5210',
    'communication': '5210',  # Vehicle comms
    'Vehicle Licensing': '5210',
    'licenses': '5210',
    'Vehicle Lease': '5300',
    'Lease Payments': '5300',
    'Vehicle Financing': '5400',  # Depreciation/Financing
    'equipment_lease': '5420',
    
    # Operating Expenses (6000-6999)
    'office_supplies': '6100',
    'Office Supplies': '6100',
    'Supplies': '6100',
    'hospitality_supplies': '6110',  # Sub-category
    'Rent': '6200',
    'Lease': '6200',
    'rent': '6200',
    'office rent': '6200',
    'Insurance': '6300',
    'General Insurance': '6300',
    'Insurance - Claim Recovery': '6300',
    'Workers Compensation': '6320',
    '6950 - WCB': '6950',
    'WCB': '6950',
    'Administrative': '6950',  # WCB/Admin
    'Professional Services': '6400',
    'Legal': '6410',
    'Accounting': '6420',
    'Consulting': '6430',
    'Bank Fees': '6500',
    'bank_fees': '6500',
    'Banking': '6500',
    'Service Charges': '6510',
    'Bank Charges & Interest': '6510',
    'Bank Charges': '6510',
    'Credit Card Fees': '6520',
    'Merchant Services': '6520',
    'Utilities': '6600',
    'utilities': '6600',
    'Telephone': '6610',
    'Internet': '6620',
    'Internet Bill Payment': '6620',
    'Advertising': '6700',
    'Marketing': '6710',
    'Meals & Entertainment': '6800',
    'meals_entertainment': '6800',
    'Meals': '6800',
    'Liquor/Entertainment': '6810',
    'Client Entertainment': '6810',
    'entertainment_beverages': '6810',
    'Entertainment': '6810',
    'CLIENT FOOD': '5900',  # Charter Supplies - Client Provisions
    'Client Food': '5900',
    'client food': '5900',
    'CLIENT BEVERAGES': '5900',  # Charter Supplies - Client Provisions
    'Client Beverages': '5900',
    'client beverages': '5900',
    'CLIENT FOOD AND BEVERAGE': '5900',
    'Client Food and Beverage': '5900',
    'Travel': '6900',
    'Business expense': '6900',
    'uncategorized_expenses': '6900',
    'mixed_use': '6900',
    'Unknown': '6900',
    'Opening Balance': '6900',
    
    # Liabilities
    'LOANS': '2110',  # Loan Payable
    'Loan Payment': '2100',
    
    # Personal/Non-deductible
    'Personal': '9999',
    'Personal Purchase': '9999',
    'Groceries - Personal': '9999',
    'Food - Personal': '9999',
    'owner_draws': '3200',  # Owner's Equity
    
    # Government
    'Government Fees': '6950',
    'government_fees': '6950',
}

def main():
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    print("=" * 100)
    print("UPDATING RECEIPTS WITH GL CODES FROM CATEGORY MAPPING")
    print("=" * 100)
    
    # Get counts before update
    cur.execute("SELECT COUNT(*) FROM receipts WHERE category IS NOT NULL AND gl_account_code IS NULL")
    missing_gl = cur.fetchone()[0]
    
    print(f"\nReceipts with category but no GL code: {missing_gl:,}")
    
    # Update each category mapping
    updated_total = 0
    skipped_categories = []
    
    for category, gl_code in sorted(CATEGORY_GL_MAPPING.items()):
        # Check how many receipts have this category but no GL code
        cur.execute("""
            SELECT COUNT(*) 
            FROM receipts 
            WHERE category = %s AND (gl_account_code IS NULL OR gl_account_code = '')
        """, (category,))
        
        count = cur.fetchone()[0]
        
        if count > 0:
            print(f"\nUpdating {count:,} receipts: '{category}' → GL {gl_code}")
            
            # Update receipts
            cur.execute("""
                UPDATE receipts
                SET gl_account_code = %s
                WHERE category = %s 
                  AND (gl_account_code IS NULL OR gl_account_code = '')
            """, (gl_code, category))
            
            updated_total += cur.rowcount
            print(f"  ✓ Updated: {cur.rowcount:,} receipts")
    
    # Find categories without mappings
    cur.execute("""
        SELECT category, COUNT(*) as cnt
        FROM receipts
        WHERE category IS NOT NULL 
          AND category != ''
          AND (gl_account_code IS NULL OR gl_account_code = '')
        GROUP BY category
        ORDER BY cnt DESC
    """)
    
    unmapped = cur.fetchall()
    
    if unmapped:
        print("\n" + "=" * 100)
        print("CATEGORIES STILL WITHOUT GL CODES")
        print("=" * 100)
        for cat, cnt in unmapped:
            print(f"  {cat:<50} {cnt:,} receipts")
            skipped_categories.append(cat)
    
    # Commit changes
    print("\n" + "=" * 100)
    print("COMMITTING CHANGES")
    print("=" * 100)
    print(f"Total receipts updated: {updated_total:,}")
    print(f"Categories mapped: {len(CATEGORY_GL_MAPPING)}")
    print(f"Unmapped categories remaining: {len(skipped_categories)}")
    
    # Ask for confirmation
    response = input("\nCommit these changes? (yes/no): ").strip().lower()
    
    if response == 'yes':
        conn.commit()
        print("\n✅ Changes committed successfully!")
        
        # Verify
        cur.execute("SELECT COUNT(*) FROM receipts WHERE category IS NOT NULL AND (gl_account_code IS NULL OR gl_account_code = '')")
        still_missing = cur.fetchone()[0]
        print(f"Receipts still missing GL codes: {still_missing:,}")
    else:
        conn.rollback()
        print("\n❌ Changes rolled back - no updates made")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
