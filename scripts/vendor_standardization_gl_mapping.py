#!/usr/bin/env python
"""Generate clean vendor list with GL code categorization and 2019 split patterns."""
import psycopg2
from psycopg2.extras import RealDictCursor
import os
import csv
from collections import defaultdict
from datetime import datetime

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password=os.environ.get('DB_PASSWORD', '***REMOVED***')
)
cur = conn.cursor(cursor_factory=RealDictCursor)

# Define GL Account mapping with parent categories
GL_MAPPING = {
    # BUSINESS EXPENSE GL CODES
    '5110': {'gl_name': 'Fuel & Gas', 'parent': 'Business Expense', 'keywords': ['fuel', 'gas', 'centex', 'shell', 'esso', 'husky']},
    '5120': {'gl_name': 'Vehicle Maintenance & Repair', 'parent': 'Business Expense', 'keywords': ['maintenance', 'repair', 'auto', 'tire', 'heffner']},
    '5300': {'gl_name': 'Office Equipment & Supplies', 'parent': 'Business Expense', 'keywords': ['office', 'staples', 'supplies']},
    '5410': {'gl_name': 'Rent', 'parent': 'Business Expense', 'keywords': ['rent', 'landlord', 'fibrenew']},
    '5430': {'gl_name': 'Office Supplies', 'parent': 'Business Expense', 'keywords': ['supplies', 'paper', 'printer']},
    '5620': {'gl_name': 'Insurance', 'parent': 'Business Expense', 'keywords': ['insurance', 'sgi', 'aviva']},
    '5630': {'gl_name': 'WCB (Workers Compensation)', 'parent': 'Business Expense', 'keywords': ['wcb', 'workers comp']},
    '5810': {'gl_name': 'Meals & Entertainment', 'parent': 'Business Expense', 'keywords': ['restaurant', 'food', 'cafe', 'tim hortons', 'mcdonalds']},
    '5850': {'gl_name': 'General Business Expense', 'parent': 'Business Expense', 'keywords': []},
    
    # PERSONAL EXPENSE GL CODES
    '5900': {'gl_name': 'Personal Expense', 'parent': 'Personal Expense', 'keywords': ['personal', 'private']},
    '5910': {'gl_name': 'Personal Meals', 'parent': 'Personal Expense', 'keywords': []},
    '5920': {'gl_name': 'Personal Shopping', 'parent': 'Personal Expense', 'keywords': ['costco', 'superstore', 'grocery']},
    
    # ASSET GL CODES
    '1010': {'gl_name': 'Checking Account', 'parent': 'Banking', 'keywords': []},
    '2020': {'gl_name': 'Notes Payable', 'parent': 'Liability', 'keywords': []},
}

print("=" * 100)
print("VENDOR STANDARDIZATION WITH GL CODE CATEGORIZATION")
print("=" * 100)

# Get all vendors with their current GL codes and patterns
print("\n1. QUERYING VENDOR DATA FROM BANKING_TRANSACTIONS...\n")

cur.execute("""
    SELECT 
        vendor_extracted,
        COUNT(*) as txn_count,
        ROUND(SUM(COALESCE(debit_amount, 0))::numeric, 2) as total_spent,
        MIN(transaction_date) as first_date,
        MAX(transaction_date) as last_date
    FROM banking_transactions
    WHERE account_number = '0228362'
    AND vendor_extracted NOT IN ('Customer', 'Square', 'Business Expense', 'Sales', 
                                 'Unknown', 'Cheque', 'Deposit', 'Transfer', 
                                 'Banking', 'Fee', 'Interest')
    AND vendor_extracted NOT LIKE '%Cheque%'
    GROUP BY vendor_extracted
    ORDER BY total_spent DESC
""")

vendors = cur.fetchall()
print(f"✓ Found {len(vendors)} unique vendors\n")

# Categorize vendors
vendor_categories = defaultdict(list)
for vendor in vendors:
    vendor_name = vendor['vendor_extracted']
    
    # Find best matching GL code based on vendor keywords
    best_gl = None
    best_match_score = 0
    
    for gl_code, gl_info in GL_MAPPING.items():
        for keyword in gl_info['keywords']:
            if keyword.lower() in vendor_name.lower():
                best_match_score += 1
    
    # Assign GL code based on best match
    for gl_code, gl_info in GL_MAPPING.items():
        match_score = 0
        for keyword in gl_info['keywords']:
            if keyword.lower() in vendor_name.lower():
                match_score += 1
        if match_score > 0 and match_score >= best_match_score:
            best_gl = gl_code
            best_match_score = match_score
    
    if not best_gl:
        best_gl = '5850'  # Default to General Business Expense
    
    gl_info = GL_MAPPING[best_gl]
    parent = gl_info['parent']
    gl_name = gl_info['gl_name']
    
    vendor_categories[f"{parent} → {best_gl} {gl_name}"].append({
        'vendor': vendor_name,
        'gl_code': best_gl,
        'gl_name': gl_name,
        'parent': parent,
        'txn_count': vendor['txn_count'],
        'total_spent': vendor['total_spent'],
        'first_date': vendor['first_date'],
        'last_date': vendor['last_date']
    })

# Display organized by parent → GL code
print("\n" + "=" * 100)
print("2. VENDOR LIST ORGANIZED BY PARENT CATEGORY → GL CODE")
print("=" * 100)

for category in sorted(vendor_categories.keys()):
    vendors_in_cat = vendor_categories[category]
    total_txns = sum(v['txn_count'] for v in vendors_in_cat)
    total_amount = sum(v['total_spent'] for v in vendors_in_cat)
    
    print(f"\n{category}")
    print(f"  📊 Subtotal: {len(vendors_in_cat)} vendors | {total_txns} transactions | ${total_amount:,.2f}")
    print("  " + "-" * 95)
    
    for vendor in sorted(vendors_in_cat, key=lambda v: v['total_spent'], reverse=True):
        print(f"    • {vendor['vendor']:45} | {vendor['txn_count']:4} txn | ${vendor['total_spent']:12,.2f} | {vendor['first_date']} to {vendor['last_date']}")

# Now check 2019 split receipt patterns
print("\n\n" + "=" * 100)
print("3. ANALYZING 2019 SPLIT RECEIPT PATTERNS (Business vs Personal)")
print("=" * 100)

cur.execute("""
    SELECT 
        vendor_name,
        COUNT(*) as receipt_count,
        COUNT(CASE WHEN business_personal IS NOT NULL THEN 1 END) as categorized,
        COUNT(CASE WHEN business_personal = 'Business' THEN 1 END) as business_only,
        COUNT(CASE WHEN business_personal = 'Personal' THEN 1 END) as personal_only,
        COUNT(CASE WHEN business_personal NOT IN ('Business', 'Personal') THEN 1 END) as split_or_mixed,
        ROUND(SUM(CASE WHEN business_personal = 'Business' THEN gross_amount ELSE 0 END)::numeric, 2) as business_amount,
        ROUND(SUM(CASE WHEN business_personal = 'Personal' THEN gross_amount ELSE 0 END)::numeric, 2) as personal_amount,
        ROUND(SUM(CASE WHEN business_personal NOT IN ('Business', 'Personal') THEN gross_amount ELSE 0 END)::numeric, 2) as split_amount
    FROM receipts
    WHERE EXTRACT(YEAR FROM receipt_date) = 2019
    AND vendor_name IS NOT NULL
    AND vendor_name != ''
    GROUP BY vendor_name
    HAVING COUNT(*) > 0
    ORDER BY receipt_count DESC
""")

split_vendors = cur.fetchall()
print(f"\n✓ Found {len(split_vendors)} vendors with 2019 receipts\n")

print("Vendors with mixed Business/Personal classification:\n")
mixed_count = 0
for row in split_vendors:
    if row['split_or_mixed'] and row['split_or_mixed'] > 0:
        mixed_count += 1
        print(f"  {row['vendor_name']:45} | Business: ${row['business_amount']:10,.2f} | Personal: ${row['personal_amount']:10,.2f}")
        if mixed_count >= 20:
            print(f"\n  ... and {len(split_vendors) - 20} more vendors with mixed classifications")
            break

# Export comprehensive CSV
print("\n\n" + "=" * 100)
print("4. EXPORTING VENDOR LIST TO CSV")
print("=" * 100)

timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
csv_path = f'l:\\limo\\reports\\vendor_standardization_gl_mapping_{timestamp}.csv'

with open(csv_path, 'w', newline='', encoding='utf-8') as csvfile:
    fieldnames = ['vendor_name', 'gl_code', 'gl_name', 'parent_category', 'txn_count', 
                  'total_spent', 'first_date', 'last_date', 'recommended_action']
    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
    
    writer.writeheader()
    for category in sorted(vendor_categories.keys()):
        for vendor in vendor_categories[category]:
            writer.writerow({
                'vendor_name': vendor['vendor'],
                'gl_code': vendor['gl_code'],
                'gl_name': vendor['gl_name'],
                'parent_category': vendor['parent'],
                'txn_count': vendor['txn_count'],
                'total_spent': vendor['total_spent'],
                'first_date': vendor['first_date'],
                'last_date': vendor['last_date'],
                'recommended_action': 'REVIEW' if vendor['txn_count'] > 100 else 'VERIFY'
            })

print(f"\n✓ Exported to: {csv_path}")

# Summary statistics
print("\n\n" + "=" * 100)
print("5. SUMMARY STATISTICS")
print("=" * 100)

cur.execute("SELECT COUNT(DISTINCT vendor_extracted) FROM banking_transactions WHERE account_number = '0228362'")
total_banking_vendors = cur.fetchone()['count']

print(f"""
Total unique vendors in banking:        {total_banking_vendors:,}
Vendors successfully categorized:       {len(vendors):,}
Total categories (Parent → GL Code):    {len(vendor_categories)}

2019 Analysis:
  - Receipts with business_personal:   {len(split_vendors)} vendors
  - Vendors with mixed classification: {mixed_count} (require review for splitting)

GL Code Distribution:
""")

for parent in ['Business Expense', 'Personal Expense', 'Banking', 'Liability']:
    parent_vendors = []
    parent_total = 0
    for category, vendors_list in vendor_categories.items():
        if parent in category:
            parent_vendors.extend(vendors_list)
            parent_total += sum(v['total_spent'] for v in vendors_list)
    
    if parent_vendors:
        print(f"  {parent:25} | {len(parent_vendors):3} vendors | ${parent_total:15,.2f}")

print("\n" + "=" * 100)
print("✓ VENDOR STANDARDIZATION COMPLETE")
print("=" * 100)

conn.close()
