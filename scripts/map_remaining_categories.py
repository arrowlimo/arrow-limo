#!/usr/bin/env python3
"""Map remaining 13 categories to GL account codes."""

import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REDACTED***'
)
cur = conn.cursor()

# Category to GL account mappings
CATEGORY_MAPPINGS = {
    'Customer Refunds': '4900',  # Sales Returns & Allowances
    'Employee Reimbursements': '5410',  # Employee Expenses
    'Equipment Rental': '5420',  # Equipment Rental
    'Internal Transfer': '1010',  # Cash & Bank Accounts (internal movement)
    'Other Income': '4950',  # Other Income
    'Owner Capital Contributions': '3100',  # Owner's Capital
    'Petty Cash': '1020',  # Petty Cash
    'Supplies': '5430',  # Office Supplies
    'Travel': '5440',  # Travel & Lodging
    'Uncategorized Expenses': '5850',  # Mixed-Use Expenses
    'Uniforms & Clothing': '5450',  # Uniforms
    'Vendor Refunds': '1010',  # Cash & Bank Accounts (refund received)
    'Waste Removal': '5460',  # Waste Disposal
}

print("="*80)
print("MAPPING REMAINING CATEGORIES TO GL ACCOUNTS")
print("="*80)

for category_name, gl_code in CATEGORY_MAPPINGS.items():
    # Get account name for display
    cur.execute("SELECT account_name FROM chart_of_accounts WHERE account_code = %s", (gl_code,))
    row = cur.fetchone()
    account_name = row[0] if row else "Unknown"
    
    # Update mapping
    cur.execute("""
        UPDATE account_categories
        SET gl_account_code = %s
        WHERE category_name = %s
    """, (gl_code, category_name))
    
    print(f"✓ {category_name:35s} → {gl_code} ({account_name})")

conn.commit()

# Verify completion
cur.execute("SELECT COUNT(*) FROM account_categories WHERE gl_account_code IS NOT NULL")
mapped = cur.fetchone()[0]

cur.execute("SELECT COUNT(*) FROM account_categories")
total = cur.fetchone()[0]

print("\n" + "="*80)
print(f"✓ COMPLETE: {mapped}/{total} categories now have GL codes")
print("="*80)

conn.close()
