#!/usr/bin/env python3
"""
Analyze all categories in receipts table and map to GL codes.
Create new GL codes if needed.
"""

import psycopg2
from collections import Counter

DB_CONFIG = {
    'host': 'localhost',
    'database': 'almsdata',
    'user': 'postgres',
    'password': '***REDACTED***'
}

conn = psycopg2.connect(**DB_CONFIG)
cur = conn.cursor()

def get_gl_description(gl_code):
    """Return description for GL code."""
    descriptions = {
        '4000': 'General Revenue',
        '4100': 'Charter Revenue',
        '4150': 'Fuel Surcharge Revenue',
        '1010': 'Cash - Checking',
        '1020': 'Cash - Savings',
        '1030': 'Petty Cash',
        '5110': 'Vehicle Fuel',
        '5120': 'Vehicle Maintenance',
        '5130': 'Vehicle Repairs',
        '5200': 'Vehicle Insurance',
        '5210': 'Vehicle Registration',
        '5300': 'Vehicle Lease Payments',
        '5400': 'Vehicle Depreciation',
        '6100': 'Office Supplies',
        '6200': 'Rent/Lease',
        '6300': 'General Insurance',
        '6310': 'Liability Insurance',
        '6320': 'Workers Compensation',
        '6400': 'Professional Services',
        '6410': 'Legal Fees',
        '6420': 'Accounting Fees',
        '6430': 'Consulting Fees',
        '6500': 'Bank Fees',
        '6510': 'Service Charges',
        '6520': 'Merchant/CC Fees',
        '6600': 'Utilities',
        '6610': 'Telephone',
        '6620': 'Internet',
        '6700': 'Advertising',
        '6710': 'Marketing',
        '6800': 'Meals & Entertainment',
        '6810': 'Entertainment Only',
        '6900': 'Travel Expenses',
        '6990': 'Other/Miscellaneous',
        '7000': 'Wages/Salaries',
        '7010': 'Driver Payroll',
        '7100': 'Employee Benefits',
        '7200': 'Payroll Taxes',
        '7210': 'CPP Contributions',
        '7220': 'EI Premiums',
        '9000': 'Internal Transfers',
        '9100': 'Deposits',
        '9200': 'Withdrawals',
        '9999': 'Personal/Non-Deductible',
    }
    return descriptions.get(gl_code, 'Unknown')

print("=" * 100)
print("ANALYZING RECEIPT CATEGORIES → GL CODE MAPPING")
print("=" * 100)

# Get all distinct categories with counts
cur.execute("""
    SELECT 
        category,
        COUNT(*) as receipt_count,
        SUM(gross_amount) as total_amount,
        COUNT(DISTINCT gl_account_code) as gl_codes_used
    FROM receipts
    WHERE category IS NOT NULL AND category != ''
    GROUP BY category
    ORDER BY receipt_count DESC
""")

categories = cur.fetchall()

print(f"\n{'Category':<40} {'Count':<10} {'Total Amount':<15} {'GL Codes'}")
print("-" * 100)

category_mapping = {}
for cat, count, amount, gl_count in categories:
    amount_str = f"${amount:,.2f}" if amount else "$0.00"
    print(f"{cat:<40} {count:<10} {amount_str:<15} {gl_count}")
    
    # Get GL codes already used for this category
    cur.execute("""
        SELECT gl_account_code, COUNT(*) 
        FROM receipts 
        WHERE category = %s AND gl_account_code IS NOT NULL
        GROUP BY gl_account_code
        ORDER BY COUNT(*) DESC
        LIMIT 5
    """, (cat,))
    
    existing_gl = cur.fetchall()
    if existing_gl:
        print(f"  → Existing GL codes: {', '.join([f'{gl}({ct})' for gl, ct in existing_gl])}")

print("\n" + "=" * 100)
print("PROPOSED GL CODE MAPPING (based on common accounting standards)")
print("=" * 100)

# Standard GL code mapping
gl_mapping = {
    # Revenue (4000-4999)
    'Income': '4000',
    'Revenue': '4000', 
    'Sales': '4000',
    'Charter Revenue': '4100',
    'Fuel Surcharge': '4150',
    
    # Assets (1000-1999)
    'Cash': '1010',
    'Checking Account': '1010',
    'Savings': '1020',
    'Petty Cash': '1030',
    
    # Vehicle/Fleet (5000-5999)
    'Fuel': '5110',
    'Vehicle Fuel': '5110',
    'Gas': '5110',
    'Diesel': '5110',
    'Vehicle Maintenance': '5120',
    'Maintenance': '5120',
    'Vehicle Repairs': '5130',
    'Repairs': '5130',
    'Vehicle Insurance': '5200',
    'Auto Insurance': '5200',
    'Vehicle Registration': '5210',
    'Vehicle Licensing': '5210',
    'Vehicle Lease': '5300',
    'Lease Payments': '5300',
    'Vehicle Depreciation': '5400',
    
    # Operating Expenses (6000-6999)
    'Office Supplies': '6100',
    'Office': '6100',
    'Supplies': '6100',
    'Rent': '6200',
    'Lease': '6200',
    'Insurance': '6300',
    'General Insurance': '6300',
    'Liability Insurance': '6310',
    'Workers Compensation': '6320',
    'WCB': '6320',
    'Professional Services': '6400',
    'Legal': '6410',
    'Accounting': '6420',
    'Consulting': '6430',
    'Bank Fees': '6500',
    'Banking': '6500',
    'Service Charges': '6510',
    'Credit Card Fees': '6520',
    'Merchant Services': '6520',
    'Utilities': '6600',
    'Telephone': '6610',
    'Internet': '6620',
    'Advertising': '6700',
    'Marketing': '6710',
    'Meals & Entertainment': '6800',
    'Meals': '6800',
    'Entertainment': '6810',
    'Travel': '6900',
    'Other Expenses': '6990',
    'Miscellaneous': '6990',
    
    # Payroll (7000-7999)
    'Wages': '7000',
    'Salaries': '7000',
    'Driver Pay': '7010',
    'Employee Benefits': '7100',
    'Payroll Taxes': '7200',
    'CPP': '7210',
    'EI': '7220',
    
    # Transfers/Internal
    'Transfer': '9000',
    'Transfers': '9000',
    'Internal Transfer': '9000',
    'Deposit': '9100',
    'Withdrawal': '9200',
    
    # Personal/Non-deductible
    'Personal': '9999',
    'Personal Purchase': '9999',
    'Owner Draw': '9999',
}

print(f"\n{'Category':<40} → {'GL Code':<10} {'Description'}")
print("-" * 100)

for cat, count, amount, gl_count in categories:
    suggested_gl = gl_mapping.get(cat, '6990')  # Default to Other Expenses
    gl_desc = get_gl_description(suggested_gl)
    print(f"{cat:<40} → {suggested_gl:<10} {gl_desc}")
    category_mapping[cat] = suggested_gl

print("\n" + "=" * 100)
print("CATEGORIES NEEDING NEW GL CODES")
print("=" * 100)

unmapped = []
for cat, count, amount, gl_count in categories:
    if cat not in gl_mapping:
        unmapped.append((cat, count, amount))

if unmapped:
    print(f"\n{'Category':<40} {'Count':<10} {'Total Amount'}")
    print("-" * 100)
    for cat, count, amount in unmapped:
        amount_str = f"${amount:,.2f}" if amount else "$0.00"
        print(f"{cat:<40} {count:<10} {amount_str}")
        print(f"  → Suggested GL: 6990 (Other Expenses) - NEEDS REVIEW")
else:
    print("\n✅ All categories have GL code mappings!")

print("\n" + "=" * 100)
print("SUMMARY")
print("=" * 100)
print(f"Total unique categories: {len(categories)}")
print(f"Categories with existing GL codes: {sum(1 for _, _, _, gl in categories if gl > 0)}")
print(f"Categories needing mapping: {len(unmapped)}")
print(f"\nTotal receipts to update: {sum(count for _, count, _, _ in categories)}")

cur.close()
conn.close()
