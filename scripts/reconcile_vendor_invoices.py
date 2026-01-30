#!/usr/bin/env python3
"""
Extract invoice/receipt data from OCR'd PDFs to reconcile vendor account balances.
Key: Match receipts to banking payments and verify running balances.
"""

import psycopg2
import re
from datetime import datetime

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()

print('='*80)
print('VENDOR INVOICE RECONCILIATION - EXTRACT & MATCH RECEIPTS')
print('='*80)
print(f'Time: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
print()

# Step 1: Get the problematic receipts from 2025-10-25
print('STEP 1: Identifying vendor invoices needing reconciliation')
print('-'*80)

cur.execute("""
    SELECT receipt_id, receipt_date, vendor_name, description, gross_amount,
           category, source_reference, banking_transaction_id
    FROM receipts
    WHERE receipt_date = '2025-10-25'
    AND (description LIKE '%Invoice%' OR description LIKE '%Delivery%')
    AND receipt_source = 'MANUAL'
    ORDER BY receipt_id
""")

invoices = cur.fetchall()
print(f'Found {len(invoices)} vendor invoices needing reconciliation:')
print()

for receipt_id, receipt_date, vendor, desc, amount, category, source_ref, bank_txn_id in invoices:
    # Extract PDF filename
    pdf_match = re.search(r'Extracted from PDF:\s*(.+?)(?:\(|\s|$)', desc)
    pdf_file = pdf_match.group(1) if pdf_match else 'Unknown'
    
    # Extract vendor/invoice info from description
    invoice_match = re.search(r'Invoice[#\s]+(\d+)', desc, re.IGNORECASE)
    invoice_num = invoice_match.group(1) if invoice_match else 'N/A'
    
    print(f"Receipt {receipt_id}:")
    print(f"  Vendor: {vendor}")
    print(f"  Amount: ${float(amount):.2f}")
    print(f"  Invoice: {invoice_num}")
    print(f"  PDF: {pdf_file}")
    print(f"  Banking Link: {'✅ LINKED' if bank_txn_id else '❌ NOT LINKED'}")
    print()

print()
print('STEP 2: Categorizing by vendor')
print('-'*80)

# Categorize vendors
cur.execute("""
    SELECT vendor_name, COUNT(*) as count, SUM(gross_amount) as total
    FROM receipts
    WHERE receipt_date = '2025-10-25'
    AND (description LIKE '%Invoice%' OR description LIKE '%Delivery%')
    AND receipt_source = 'MANUAL'
    GROUP BY vendor_name
    ORDER BY total DESC
""")

print(f"{'Vendor':40} | {'Count':5} | {'Total Amount':15}")
print('-'*70)
for vendor, count, total in cur.fetchall():
    total_val = float(total) if total else 0.0
    print(f'{vendor:40} | {count:5} | ${total_val:>14,.2f}')

print()
print('='*80)
print('NEXT STEPS FOR RECONCILIATION')
print('='*80)
print()
print('1. Manual Data Extraction from PDFs:')
print('   - Heffner lease invoices: Extract lease amount + tax + deposit')
print('   - CMB Insurance: Extract premium + balance owed')
print('   - Other: Extract invoice # and account balance')
print()
print('2. Link to Banking:')
print('   - Search for corresponding HEFFNER, CMB payments in banking_transactions')
print('   - Match by vendor name + date range + amount')
print()
print('3. Verify Account Balances:')
print('   - Sum all payments to each vendor from banking')
print('   - Compare to balance shown on latest invoice')
print('   - Flag discrepancies for investigation')
print()
print('4. Update Receipts:')
print('   - Link banking_transaction_id to each receipt')
print('   - Update vendor_name with canonical names (HEFFNER, CMB INSURANCE)')
print('   - Mark receipt_source as appropriate (BANKING, MANUAL, etc.)')
print()

cur.close()
conn.close()
