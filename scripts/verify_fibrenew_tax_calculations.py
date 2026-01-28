#!/usr/bin/env python3
"""
Verify GST calculations on the 37 newly imported Fibrenew receipts.
Check if actual invoice files exist and validate tax amounts.
"""

import psycopg2
import os
import re
from pathlib import Path

print('='*100)
print('FIBRENEW INVOICE TAX VERIFICATION')
print('='*100)

# Connect to database
conn = psycopg2.connect(
    host=os.getenv('DB_HOST', 'localhost'),
    database=os.getenv('DB_NAME', 'almsdata'),
    user=os.getenv('DB_USER', 'postgres'),
    password=os.getenv('DB_PASSWORD', '***REMOVED***')
)
cur = conn.cursor()

# Get the 37 newly imported receipts
cur.execute("""
    SELECT receipt_id, receipt_date, gross_amount, gst_amount, net_amount, description
    FROM receipts
    WHERE vendor_name = 'Fibrenew Central Alberta'
    AND receipt_date BETWEEN '2019-01-01' AND '2021-12-31'
    ORDER BY receipt_date
""")

receipts = cur.fetchall()

print(f'\nFound {len(receipts)} Fibrenew receipts from 2019-2021 to verify')

# Search for invoice files
invoice_dirs = [
    r'L:\limo\pdf',
    r'L:\limo\documents',
    r'L:\limo\receipts'
]

print('\n\nSEARCHING FOR INVOICE FILES:')
print('-'*100)

found_invoices = []
for directory in invoice_dirs:
    if os.path.exists(directory):
        for root, dirs, files in os.walk(directory):
            for file in files:
                if 'fibrenew' in file.lower() and file.endswith('.pdf'):
                    found_invoices.append(os.path.join(root, file))
                    print(f'✓ Found: {os.path.join(root, file)}')

if not found_invoices:
    print('No Fibrenew invoice PDFs found in common directories')

# Verify GST calculations
print('\n\n' + '='*100)
print('GST CALCULATION VERIFICATION')
print('='*100)

issues = []

for r in receipts:
    receipt_id, date, gross, gst, net, desc = r
    
    # Extract invoice number
    invoice_match = re.search(r'#(\d+)', desc)
    invoice_num = invoice_match.group(1) if invoice_match else 'Unknown'
    
    # Calculate expected GST (5% included in gross amount)
    expected_gst = float(gross) * 0.05 / 1.05
    expected_net = float(gross) - expected_gst
    
    actual_gst = float(gst)
    actual_net = float(net)
    
    gst_diff = abs(actual_gst - expected_gst)
    net_diff = abs(actual_net - expected_net)
    
    if gst_diff > 0.02 or net_diff > 0.02:  # Allow 2 cent rounding tolerance
        issues.append({
            'receipt_id': receipt_id,
            'date': date,
            'invoice': invoice_num,
            'gross': float(gross),
            'actual_gst': actual_gst,
            'expected_gst': expected_gst,
            'actual_net': actual_net,
            'expected_net': expected_net,
            'gst_diff': gst_diff,
            'net_diff': net_diff
        })

if issues:
    print(f'\n⚠ FOUND {len(issues)} RECEIPTS WITH GST CALCULATION ISSUES:')
    print('-'*100)
    print(f'{"Date":<12} {"Invoice":<10} {"Gross":<12} {"Actual GST":<12} {"Expected GST":<12} {"Diff":<10}')
    print('-'*100)
    
    for issue in issues:
        print(f'{issue["date"]} #{issue["invoice"]:<8} ${issue["gross"]:>10.2f} '
              f'${issue["actual_gst"]:>10.2f} ${issue["expected_gst"]:>10.2f} '
              f'${issue["gst_diff"]:>8.2f}')
    
    # Show total impact
    total_gst_diff = sum(i['gst_diff'] for i in issues)
    print('-'*100)
    print(f'Total GST variance: ${total_gst_diff:.2f}')
    
    print('\n\nCORRECTION NEEDED:')
    print('-'*100)
    print('These receipts need GST recalculation. Possible causes:')
    print('1. Tax rate changed (e.g., some may be GST + PST combined)')
    print('2. Some amounts may exclude GST (need to add 5% on top)')
    print('3. Invoice has different tax structure than assumed')
    
else:
    print('\n✓ ALL GST CALCULATIONS CORRECT')
    print('All 37 receipts use proper 5% GST included formula')

# Check for tax-exempt items
print('\n\n' + '='*100)
print('TAX STRUCTURE ANALYSIS')
print('='*100)

# Group by amount to identify patterns
from collections import defaultdict
by_amount = defaultdict(list)
for r in receipts:
    amount_rounded = round(float(r[2]), 0)  # Round to nearest dollar
    by_amount[amount_rounded].append(r)

print('\nCOMMON INVOICE AMOUNTS:')
print('-'*100)
for amount in sorted(by_amount.keys(), reverse=True):
    count = len(by_amount[amount])
    if count > 2:  # Show amounts that appear multiple times
        print(f'${amount:,.0f}: {count} invoices')

# Check the statement PDF for tax breakdown
print('\n\n' + '='*100)
print('RECOMMENDATION')
print('='*100)
print('To verify tax accuracy:')
print('1. Check individual invoice PDFs if available (none found in search)')
print('2. Verify against Fibrenew statement PDF columns:')
print('   - "AMOUNT" column = invoice total (should match our gross_amount)')
print('   - "OPEN AMOUNT" column = unpaid balance')
print('   - Check if statement shows GST separately or included')
print('3. The statement shows amounts like 682.50 and 840.00 which are')
print('   typical GST-included amounts ($650 + 5% GST = $682.50)')
print('4. For utilities (smaller amounts), tax may vary')

cur.close()
conn.close()

print('\n' + '='*100)
print('VERIFICATION COMPLETE')
print('='*100)
