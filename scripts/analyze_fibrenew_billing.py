#!/usr/bin/env python3
"""
Analyze Fibrenew billing PDF and compare to almsdata records.
"""

import psycopg2
import os
import PyPDF2
import re
from datetime import datetime
from collections import defaultdict

# Extract text from PDF
pdf_path = r'L:\limo\pdf\2012\Statement from_Fibrenew_Central_Alberta.pdf'

print('='*100)
print('FIBRENEW BILLING ANALYSIS')
print('='*100)

print('\nExtracting text from PDF...')
with open(pdf_path, 'rb') as f:
    pdf = PyPDF2.PdfReader(f)
    text = ''
    for page in pdf.pages:
        text += page.extract_text()

print(f'\nExtracted {len(text)} characters from {len(pdf.pages)} pages')

# Look for amounts and dates
amount_pattern = re.compile(r'\$[\d,]+\.\d{2}')
date_pattern = re.compile(r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}')

amounts = amount_pattern.findall(text)
dates = date_pattern.findall(text)

print(f'\nFound {len(amounts)} amounts in PDF')
print(f'Found {len(dates)} dates in PDF')

# Show first 2000 characters to understand structure
print('\n' + '='*100)
print('PDF TEXT SAMPLE (first 2000 chars):')
print('='*100)
print(text[:2000])

# Try to parse invoice lines
lines = text.split('\n')
invoice_pattern = re.compile(r'INV.*?\$[\d,]+\.\d{2}', re.IGNORECASE)

print('\n' + '='*100)
print('POTENTIAL INVOICE LINES:')
print('='*100)
invoice_lines = []
for line in lines:
    if invoice_pattern.search(line) or ('$' in line and any(d in line for d in ['2012', '2013', '2014', '2015', '2016', '2017', '2018', '2019', '2020', '2021', '2022', '2023', '2024'])):
        print(line.strip())
        invoice_lines.append(line.strip())

# Now check almsdata for Fibrenew records
conn = psycopg2.connect(
    host=os.getenv('DB_HOST', 'localhost'),
    database=os.getenv('DB_NAME', 'almsdata'),
    user=os.getenv('DB_USER', 'postgres'),
    password=os.getenv('DB_PASSWORD', '***REMOVED***')
)
cur = conn.cursor()

print('\n\n' + '='*100)
print('ALMSDATA FIBRENEW RECORDS')
print('='*100)

# Search receipts
print('\n1. RECEIPTS TABLE:')
print('-'*100)
cur.execute("""
    SELECT receipt_id, receipt_date, vendor_name, gross_amount, category, description
    FROM receipts
    WHERE LOWER(vendor_name) LIKE '%fibrenew%'
       OR LOWER(description) LIKE '%fibrenew%'
    ORDER BY receipt_date
""")

receipts = cur.fetchall()
print(f'Found {len(receipts)} receipts with Fibrenew:')
total_receipts = 0
for r in receipts:
    print(f'  {r[1]} - ${r[3]:,.2f} - {r[1]} - {r[4]} - {r[5][:50] if r[5] else ""}')
    total_receipts += r[3]
print(f'\nTotal Receipts: ${total_receipts:,.2f}')

# Search banking_transactions
print('\n2. BANKING TRANSACTIONS:')
print('-'*100)
cur.execute("""
    SELECT transaction_id, transaction_date, description, debit_amount, credit_amount
    FROM banking_transactions
    WHERE LOWER(description) LIKE '%fibrenew%'
       OR LOWER(vendor_extracted) LIKE '%fibrenew%'
    ORDER BY transaction_date
""")

banking = cur.fetchall()
print(f'Found {len(banking)} banking transactions with Fibrenew:')
total_banking_debit = 0
total_banking_credit = 0
for b in banking:
    amount = b[3] if b[3] else -b[4] if b[4] else 0
    print(f'  {b[1]} - ${amount:,.2f} - {b[2][:60]}')
    if b[3]:
        total_banking_debit += b[3]
    if b[4]:
        total_banking_credit += b[4]
print(f'\nTotal Banking Debits: ${total_banking_debit:,.2f}')
print(f'Total Banking Credits: ${total_banking_credit:,.2f}')

# Search payments (in case rent was paid via customer payments)
print('\n3. PAYMENTS TABLE:')
print('-'*100)
cur.execute("""
    SELECT payment_id, payment_date, amount, notes
    FROM payments
    WHERE LOWER(notes) LIKE '%fibrenew%'
    ORDER BY payment_date
""")

payments = cur.fetchall()
print(f'Found {len(payments)} payments with Fibrenew:')
total_payments = 0
for p in payments:
    print(f'  {p[1]} - ${p[2]:,.2f} - {p[3][:60] if p[3] else ""}')
    total_payments += p[2]
print(f'\nTotal Payments: ${total_payments:,.2f}')

# Search charters (trade of services)
print('\n4. CHARTERS TABLE (Fibrenew trades):')
print('-'*100)
cur.execute("""
    SELECT c.reserve_number, c.charter_date, cl.client_name, c.total_amount_due, c.paid_amount, c.notes
    FROM charters c
    LEFT JOIN clients cl ON c.client_id = cl.client_id
    WHERE LOWER(c.notes) LIKE '%fibrenew%'
       OR LOWER(cl.client_name) LIKE '%fibrenew%'
    ORDER BY c.charter_date
""")

charters = cur.fetchall()
print(f'Found {len(charters)} charters related to Fibrenew:')
total_charters = 0
for c in charters:
    print(f'  {c[0]} - {c[1]} - {c[2]} - Due: ${c[3]:,.2f} Paid: ${c[4]:,.2f}')
    if c[5]:
        print(f'    Notes: {c[5][:80]}')
    total_charters += c[3]
print(f'\nTotal Charter Amount Due: ${total_charters:,.2f}')

# Search email_financial_events
print('\n5. EMAIL FINANCIAL EVENTS:')
print('-'*100)
cur.execute("""
    SELECT id, email_date, event_type, amount, notes
    FROM email_financial_events
    WHERE LOWER(notes) LIKE '%fibrenew%'
       OR LOWER(entity) LIKE '%fibrenew%'
    ORDER BY email_date
""")

emails = cur.fetchall()
print(f'Found {len(emails)} email events with Fibrenew:')
total_emails = 0
for e in emails:
    print(f'  {e[1]} - {e[2]} - ${e[3]:,.2f} - {e[4][:60] if e[4] else ""}')
    total_emails += e[3] if e[3] else 0
print(f'\nTotal Email Events: ${total_emails:,.2f}')

print('\n\n' + '='*100)
print('SUMMARY COMPARISON')
print('='*100)
print(f'PDF Invoice Lines Found: {len(invoice_lines)}')
print(f'PDF Amounts Found: {len(amounts)}')
print(f'\nALMSDATA RECORDS:')
print(f'  Receipts: {len(receipts)} records, ${total_receipts:,.2f}')
print(f'  Banking: {len(banking)} records, ${total_banking_debit:,.2f} debits, ${total_banking_credit:,.2f} credits')
print(f'  Payments: {len(payments)} records, ${total_payments:,.2f}')
print(f'  Charters: {len(charters)} records, ${total_charters:,.2f}')
print(f'  Email Events: {len(emails)} records, ${total_emails:,.2f}')

cur.close()
conn.close()
