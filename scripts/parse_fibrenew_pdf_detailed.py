#!/usr/bin/env python3
"""
Parse Fibrenew PDF statement line by line and match to almsdata receipts.
"""

import psycopg2
import os
import PyPDF2
import re
from datetime import datetime

# Extract and parse PDF
pdf_path = r'L:\limo\pdf\2012\Statement from_Fibrenew_Central_Alberta.pdf'

print('='*100)
print('FIBRENEW PDF STATEMENT PARSING')
print('='*100)

with open(pdf_path, 'rb') as f:
    pdf = PyPDF2.PdfReader(f)
    text = ''
    for page in pdf.pages:
        text += page.extract_text() + '\n'

# Parse invoice lines
# Format: DD/MM/YYYY Invoice #XXXX: Due DD/MM/YYYY. amount1  amount2
invoice_pattern = re.compile(r'(\d{2}/\d{2}/\d{4})\s+Invoice\s+#(\d+):\s+Due\s+\d{2}/\d{2}/\d{4}\.\s+([\d.]+)\s+([\d.]+)')

invoices = []
for match in invoice_pattern.finditer(text):
    date_str = match.group(1)
    invoice_num = match.group(2)
    amount1 = float(match.group(3))
    amount2 = float(match.group(4))
    
    # Parse date DD/MM/YYYY
    try:
        date_obj = datetime.strptime(date_str, '%d/%m/%Y')
        invoices.append({
            'date': date_obj.date(),
            'invoice': invoice_num,
            'amount1': amount1,
            'amount2': amount2,
            'total': amount1  # First amount is the invoice total
        })
    except:
        pass

print(f'\nParsed {len(invoices)} invoices from PDF')

if invoices:
    # Summary by year
    from collections import defaultdict
    by_year = defaultdict(lambda: {'count': 0, 'total': 0})
    for inv in invoices:
        year = inv['date'].year
        by_year[year]['count'] += 1
        by_year[year]['total'] += inv['total']
    
    print('\nPDF SUMMARY BY YEAR:')
    print('-'*100)
    for year in sorted(by_year.keys()):
        print(f'{year}: {by_year[year]["count"]} invoices, ${by_year[year]["total"]:,.2f}')
    
    # Show first 10 and last 10
    print('\n\nFIRST 10 INVOICES:')
    print('-'*100)
    for inv in invoices[:10]:
        print(f'{inv["date"]} - Invoice #{inv["invoice"]} - ${inv["total"]:,.2f}')
    
    print('\n\nLAST 10 INVOICES:')
    print('-'*100)
    for inv in invoices[-10:]:
        print(f'{inv["date"]} - Invoice #{inv["invoice"]} - ${inv["total"]:,.2f}')

# Now compare to almsdata receipts
conn = psycopg2.connect(
    host=os.getenv('DB_HOST', 'localhost'),
    database=os.getenv('DB_NAME', 'almsdata'),
    user=os.getenv('DB_USER', 'postgres'),
    password=os.getenv('DB_PASSWORD', '***REDACTED***')
)
cur = conn.cursor()

print('\n\n' + '='*100)
print('MATCHING TO ALMSDATA RECEIPTS')
print('='*100)

# Get all Fibrenew receipts
cur.execute("""
    SELECT receipt_id, receipt_date, gross_amount, description
    FROM receipts
    WHERE LOWER(vendor_name) LIKE '%fibrenew%'
       OR LOWER(description) LIKE '%fibrenew%'
    ORDER BY receipt_date
""")

receipts = cur.fetchall()
receipt_map = {}
for r in receipts:
    key = f"{r[1]}_{r[2]:.2f}"
    if key not in receipt_map:
        receipt_map[key] = []
    receipt_map[key].append(r)

# Match invoices to receipts
matched = 0
unmatched_pdf = []
unmatched_db = list(receipts)

for inv in invoices:
    key = f"{inv['date']}_{inv['total']:.2f}"
    if key in receipt_map:
        matched += 1
        # Remove from unmatched list
        for r in receipt_map[key]:
            if r in unmatched_db:
                unmatched_db.remove(r)
    else:
        unmatched_pdf.append(inv)

print(f'\nMATCHING RESULTS:')
print('-'*100)
print(f'PDF Invoices: {len(invoices)}')
print(f'Database Receipts: {len(receipts)}')
print(f'Matched: {matched}')
print(f'Unmatched PDF Invoices: {len(unmatched_pdf)}')
print(f'Unmatched Database Receipts: {len(unmatched_db)}')

if unmatched_pdf:
    print('\n\nUNMATCHED PDF INVOICES (not in database):')
    print('-'*100)
    for inv in unmatched_pdf[:20]:  # Show first 20
        print(f'{inv["date"]} - Invoice #{inv["invoice"]} - ${inv["total"]:,.2f}')
    if len(unmatched_pdf) > 20:
        print(f'... and {len(unmatched_pdf) - 20} more')

if unmatched_db:
    print('\n\nUNMATCHED DATABASE RECEIPTS (not in PDF):')
    print('-'*100)
    for r in unmatched_db[:20]:  # Show first 20
        print(f'{r[1]} - ${r[2]:,.2f} - {r[3][:60] if r[3] else ""}')
    if len(unmatched_db) > 20:
        print(f'... and {len(unmatched_db) - 20} more')

# Summary by year for unmatched
if unmatched_pdf:
    print('\n\nUNMATCHED PDF INVOICES BY YEAR:')
    print('-'*100)
    by_year_unmatched = defaultdict(lambda: {'count': 0, 'total': 0})
    for inv in unmatched_pdf:
        year = inv['date'].year
        by_year_unmatched[year]['count'] += 1
        by_year_unmatched[year]['total'] += inv['total']
    
    for year in sorted(by_year_unmatched.keys()):
        print(f'{year}: {by_year_unmatched[year]["count"]} invoices, ${by_year_unmatched[year]["total"]:,.2f}')

print('\n\n' + '='*100)
print('CONCLUSION')
print('='*100)
if len(unmatched_pdf) == 0:
    print('✓ ALL PDF invoices are captured in almsdata')
elif len(unmatched_pdf) < len(invoices) * 0.1:
    print(f'✓ {matched}/{len(invoices)} matched ({matched/len(invoices)*100:.1f}%) - EXCELLENT coverage')
    print(f'  Only {len(unmatched_pdf)} invoices need to be added')
else:
    print(f'⚠ {matched}/{len(invoices)} matched ({matched/len(invoices)*100:.1f}%)')
    print(f'  {len(unmatched_pdf)} invoices missing from database')

cur.close()
conn.close()
