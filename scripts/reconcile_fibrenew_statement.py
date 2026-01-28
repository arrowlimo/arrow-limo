#!/usr/bin/env python3
"""
Parse the full Fibrenew statement PDF and reconcile with almsdata.
The Fibrenew records are authoritative - adjust our data to match.
"""

import psycopg2
import os
import PyPDF2
import re
from datetime import datetime
from decimal import Decimal

pdf_path = r'L:\limo\pdf\2012\Statement from_Fibrenew_Central_Alberta.pdf'

print('='*100)
print('FIBRENEW STATEMENT RECONCILIATION')
print('='*100)

# Extract PDF text
with open(pdf_path, 'rb') as f:
    pdf = PyPDF2.PdfReader(f)
    full_text = ''
    for page in pdf.pages:
        full_text += page.extract_text() + '\n'

# Parse the statement
# Columns: DATE | DESCRIPTION | AMOUNT | OPEN AMOUNT
# Format: DD/MM/YYYY Invoice #XXXX: Due DD/MM/YYYY. amount open_amount

invoice_pattern = re.compile(r'(\d{2}/\d{2}/\d{4})\s+Invoice\s+#(\d+):\s+Due\s+\d{2}/\d{2}/\d{4}\.\s+([\d.]+)\s+([\d.]+)')

invoices = []
for match in invoice_pattern.finditer(full_text):
    date_str = match.group(1)  # DD/MM/YYYY
    invoice_num = match.group(2)
    amount = Decimal(match.group(3))
    open_amount = Decimal(match.group(4))
    
    try:
        date_obj = datetime.strptime(date_str, '%d/%m/%Y')
        invoices.append({
            'date': date_obj.date(),
            'invoice': invoice_num,
            'amount': amount,
            'open_amount': open_amount
        })
    except:
        pass

print(f'\nParsed {len(invoices)} invoices from Fibrenew statement')

# Group by year
from collections import defaultdict
by_year = defaultdict(lambda: {'count': 0, 'total': Decimal('0')})
for inv in invoices:
    year = inv['date'].year
    by_year[year]['count'] += 1
    by_year[year]['total'] += inv['amount']

print('\nFIBRENEW STATEMENT BY YEAR:')
print('-'*100)
for year in sorted(by_year.keys()):
    print(f'{year}: {by_year[year]["count"]} invoices, ${by_year[year]["total"]:,.2f}')

# Connect to database
conn = psycopg2.connect(
    host=os.getenv('DB_HOST', 'localhost'),
    database=os.getenv('DB_NAME', 'almsdata'),
    user=os.getenv('DB_USER', 'postgres'),
    password=os.getenv('DB_PASSWORD', '***REMOVED***')
)
cur = conn.cursor()

# Get existing Fibrenew receipts
cur.execute("""
    SELECT receipt_id, receipt_date, gross_amount, description, category
    FROM receipts
    WHERE LOWER(vendor_name) LIKE '%fibrenew%'
       OR LOWER(description) LIKE '%fibrenew%'
    ORDER BY receipt_date
""")

existing_receipts = cur.fetchall()

# Build lookup map
receipt_map = {}
for r in existing_receipts:
    key = f"{r[1]}_{float(r[2]):.2f}"
    if key not in receipt_map:
        receipt_map[key] = []
    receipt_map[key].append(r)

print(f'\nExisting Fibrenew receipts in database: {len(existing_receipts)}')

# Find matches and gaps
matched = []
missing_from_db = []

for inv in invoices:
    key = f"{inv['date']}_{float(inv['amount']):.2f}"
    if key in receipt_map:
        matched.append(inv)
    else:
        missing_from_db.append(inv)

print(f'\nMatched invoices: {len(matched)}')
print(f'Missing from database: {len(missing_from_db)}')

if missing_from_db:
    print('\n\nMISSING INVOICES (need to add):')
    print('-'*100)
    print(f'{"Date":<12} {"Invoice":<12} {"Amount":<12} {"Open":<12}')
    print('-'*100)
    
    for inv in missing_from_db[:30]:  # Show first 30
        print(f'{inv["date"]} #{inv["invoice"]:<10} ${inv["amount"]:>10.2f} ${inv["open_amount"]:>10.2f}')
    
    if len(missing_from_db) > 30:
        print(f'... and {len(missing_from_db) - 30} more')
    
    # Calculate missing by year
    missing_by_year = defaultdict(lambda: {'count': 0, 'total': Decimal('0')})
    for inv in missing_from_db:
        year = inv['date'].year
        missing_by_year[year]['count'] += 1
        missing_by_year[year]['total'] += inv['amount']
    
    print('\n\nMISSING BY YEAR:')
    print('-'*100)
    for year in sorted(missing_by_year.keys()):
        print(f'{year}: {missing_by_year[year]["count"]} invoices, ${missing_by_year[year]["total"]:,.2f}')

# Prepare import
print('\n\n' + '='*100)
print('IMPORT PLAN')
print('='*100)

if missing_from_db:
    print(f'\nWill create {len(missing_from_db)} new receipt records')
    print('\nSample records to create:')
    print('-'*100)
    
    for inv in missing_from_db[:5]:
        print(f'\nDate: {inv["date"]}')
        print(f'Vendor: Fibrenew Central Alberta')
        print(f'Description: Invoice #{inv["invoice"]} - Office rent/utilities')
        print(f'Gross Amount: ${inv["amount"]:.2f}')
        print(f'GST (5% included): ${float(inv["amount"]) * 0.05 / 1.05:.2f}')
        print(f'Net Amount: ${float(inv["amount"]) / 1.05:.2f}')
        print(f'Category: Rent')
else:
    print('\n✓ All Fibrenew invoices already captured in database!')

# Show summary
print('\n\n' + '='*100)
print('SUMMARY')
print('='*100)
print(f'Fibrenew Statement: {len(invoices)} invoices')
print(f'Already in Database: {len(matched)} invoices')
print(f'Need to Import: {len(missing_from_db)} invoices')

if len(missing_from_db) > 0:
    total_missing = sum(inv['amount'] for inv in missing_from_db)
    print(f'Total Amount Missing: ${total_missing:,.2f}')

cur.close()
conn.close()

# Save missing invoices to file for import
if missing_from_db:
    import csv
    output_file = r'L:\limo\data\fibrenew_missing_invoices.csv'
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['date', 'invoice', 'amount', 'open_amount'])
        writer.writeheader()
        writer.writerows(missing_from_db)
    print(f'\n✓ Saved missing invoices to: {output_file}')
