#!/usr/bin/env python3
"""Generate unique vendors grouped by category for manual review."""

import psycopg2
import os
from datetime import datetime

conn = psycopg2.connect(
    host="localhost",
    database="almsdata",
    user="postgres",
    password=os.environ.get('DB_PASSWORD')
)
cur = conn.cursor()

# Query all unique vendors
cur.execute("""
    SELECT 
        vendor_extracted,
        COUNT(*) as count,
        ROUND(SUM(COALESCE(debit_amount, 0))::numeric, 2) as total_spent,
        MIN(transaction_date) as first_date,
        MAX(transaction_date) as last_date
    FROM banking_transactions
    WHERE account_number = '0228362'
    AND vendor_extracted NOT IN (
        'Customer', 'Square', 'Business Expense', 'Sales May 2012', 
        'Sales Sept 2012', 'June 2012 Sales', 'Unknown'
    )
    AND vendor_extracted NOT LIKE '%Cheque%'
    GROUP BY vendor_extracted
    ORDER BY vendor_extracted;
""")

vendors = cur.fetchall()

# Categorize vendors
categories = {
    'Automotive & Parts': [],
    'Fuel & Gas': [],
    'Liquor Stores': [],
    'Restaurants & Food': [],
    'Insurance': [],
    'Office & Supplies': [],
    'Finance & Money Services': [],
    'Services & Utilities': [],
    'Retail Stores': [],
    'Government & Professional': [],
    'Personal & Misc': [],
}

# Keyword mappings for categorization
auto_keywords = ['auto', 'tire', 'brake', 'automotive', 'car', 'parts', 'eries', 'vibe', 'midas', 'canadian tire']
fuel_keywords = ['centex', 'shell', 'esso', 'husky', 'fas gas', 'flying j', 'domo gas', 'co-op']
liquor_keywords = ['liquor', 'liquor barn', 'plaza', 'global', 'uptown', 'one stop', 'sobey', 'buybuy']
restaurant_keywords = ['restaurant', 'pizza', 'taco', 'sushi', 'grill', 'tony', 'phils', 'shone', 'romas', 'a&w', 'tim horton', 'mcdonalds']
insurance_keywords = ['insurance', 'jevco', 'aviva', 'optimum']
office_keywords = ['staples', 'office', 'supplies', 'copies']
finance_keywords = ['ifs', 'money mart', 'finance', 'lender', 'heffner', 'receiver', 'revenue']
utility_keywords = ['telus', 'enmax', 'hydro', 'communication', 'phone']
retail_keywords = ['best buy', 'future shop', 'shoppers', 'bay', 'warehouse', 'costco', 'safeway', 'bed bath', 'depot']
government_keywords = ['registrar', 'receiver general', 'government', 'minister', 'parking']

def categorize(vendor):
    vendor_lower = vendor.lower()
    
    for kw in auto_keywords:
        if kw in vendor_lower:
            return 'Automotive & Parts'
    for kw in fuel_keywords:
        if kw in vendor_lower:
            return 'Fuel & Gas'
    for kw in liquor_keywords:
        if kw in vendor_lower:
            return 'Liquor Stores'
    for kw in restaurant_keywords:
        if kw in vendor_lower:
            return 'Restaurants & Food'
    for kw in insurance_keywords:
        if kw in vendor_lower:
            return 'Insurance'
    for kw in office_keywords:
        if kw in vendor_lower:
            return 'Office & Supplies'
    for kw in finance_keywords:
        if kw in vendor_lower:
            return 'Finance & Money Services'
    for kw in utility_keywords:
        if kw in vendor_lower:
            return 'Services & Utilities'
    for kw in retail_keywords:
        if kw in vendor_lower:
            return 'Retail Stores'
    for kw in government_keywords:
        if kw in vendor_lower:
            return 'Government & Professional'
    
    return 'Personal & Misc'

for vendor, count, total, first, last in vendors:
    category = categorize(vendor)
    categories[category].append((vendor, count, total, first, last))

# Sort each category by count (descending)
for cat in categories:
    categories[cat].sort(key=lambda x: x[1], reverse=True)

# Generate report
print("\n" + "="*100)
print("UNIQUE BANKING VENDORS BY CATEGORY - ORGANIZED FOR REVIEW")
print("="*100)

total_vendors = 0
for category in sorted(categories.keys()):
    if categories[category]:
        print(f"\n{'─'*100}")
        print(f"📋 {category.upper()}")
        print(f"{'─'*100}")
        print(f"{'Vendor Name':<50} {'Count':>6} {'Total Spent':>15} {'Date Range':<20}")
        print("─"*100)
        
        for vendor, count, total, first, last in categories[category]:
            date_range = f"{first} to {last}"
            print(f"{vendor:<50} {count:>6} ${total:>14,.2f} {date_range:<20}")
            total_vendors += 1

print(f"\n{'='*100}")
print(f"TOTAL UNIQUE VENDORS: {total_vendors}")
print(f"{'='*100}\n")

# Export to CSV
csv_filename = f"l:\\limo\\reports\\unique_vendors_by_category_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
with open(csv_filename, 'w', encoding='utf-8') as f:
    f.write("Category,Vendor Name,Count,Total Spent,First Date,Last Date\n")
    for category in sorted(categories.keys()):
        for vendor, count, total, first, last in categories[category]:
            f.write(f"{category},{vendor},{count},${total:,.2f},{first},{last}\n")

print(f"✓ Exported to CSV: {csv_filename}\n")

conn.close()
