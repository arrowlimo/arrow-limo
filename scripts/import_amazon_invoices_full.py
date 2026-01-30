#!/usr/bin/env python3
"""
Full Amazon invoice import to receipts table.
Supports --write flag to actually create database records.
"""
import os
import sys
import psycopg2
from pathlib import Path
from datetime import datetime
import re
import hashlib
from PyPDF2 import PdfReader

# Parse arguments
write_mode = '--write' in sys.argv

conn = psycopg2.connect(
    host=os.getenv('DB_HOST', 'localhost'),
    database=os.getenv('DB_NAME', 'almsdata'),
    user=os.getenv('DB_USER', 'postgres'),
    password=os.getenv('DB_PASSWORD', '***REDACTED***'),
)
cur = conn.cursor()

mode_text = "WRITE MODE" if write_mode else "DRY-RUN MODE"
print("\n" + "="*80)
print(f"AMAZON INVOICE IMPORT - {mode_text}")
print("="*80 + "\n")

# Get all PDFs
pdf_folder = Path(r"L:\limo\mbna amazon")
pdfs = sorted(pdf_folder.glob("*.pdf"))

invoices = []
errors = []

for pdf_path in pdfs:
    try:
        pdf = PdfReader(str(pdf_path))
        page = pdf.pages[0]
        text = page.extract_text()
        
        if not text:
            continue
        
        # Extract invoice date
        date_match = re.search(r'Invoice date.*?:\s*(\d{1,2})\s+(\w+)\s+(\d{4})', text, re.IGNORECASE)
        invoice_date = None
        if date_match:
            day, month_str, year = date_match.groups()
            try:
                invoice_date = datetime.strptime(f"{day} {month_str} {year}", "%d %B %Y").date()
            except ValueError:
                try:
                    invoice_date = datetime.strptime(f"{day} {month_str} {year}", "%d %b %Y").date()
                except:
                    pass
        
        # Extract amount
        amount_match = re.search(r'Total.*?payable.*?[:=\s]+\$?([\d,]+\.?\d*)', text, re.IGNORECASE | re.DOTALL)
        if not amount_match:
            amount_match = re.search(r'Total à payer.*?[:=\s]+\$?([\d,]+\.?\d*)', text, re.IGNORECASE)
        
        amount = None
        if amount_match:
            amount_str = amount_match.group(1).replace(',', '')
            try:
                amount = float(amount_str)
            except:
                pass
        
        # Description and vehicle reference
        description = pdf_path.stem
        vehicle_match = re.search(r'(L\d{1,2}|E450)', description, re.IGNORECASE)
        vehicle_ref = vehicle_match.group(1) if vehicle_match else None
        
        # Hash for duplicate detection
        if invoice_date and amount:
            hash_input = f"amazon|{invoice_date}|{amount:.2f}".encode('utf-8')
            source_hash = hashlib.sha256(hash_input).hexdigest()
        else:
            source_hash = hashlib.sha256(description.encode('utf-8')).hexdigest()
        
        # Check existing
        cur.execute("SELECT receipt_id FROM receipts WHERE source_hash = %s", (source_hash,))
        if cur.fetchone():
            errors.append(f"SKIP (duplicate): {pdf_path.name}")
            continue
        
        invoices.append({
            'filename': pdf_path.name,
            'description': description,
            'invoice_date': invoice_date or datetime.now().date(),
            'amount': amount or 0,
            'vehicle_ref': vehicle_ref,
            'source_hash': source_hash,
        })
    
    except Exception as e:
        errors.append(f"ERROR in {pdf_path.name}: {str(e)}")

# Calculate GST (5% included for Alberta)
def calc_gst(gross_amount):
    gst = gross_amount * 0.05 / 1.05
    net = gross_amount - gst
    return round(gst, 2), round(net, 2)

total_imported = 0
total_amount = 0

if write_mode:
    print(f"Creating {len(invoices)} receipts in database...\n")
    
    for inv in invoices:
        gst_amt, net_amt = calc_gst(inv['amount'])
        
        # Tag as David-paid
        description_tagged = f"{inv['description']} (David paid - Amazon invoice)"
        
        cur.execute("""
            INSERT INTO receipts (
                receipt_date, vendor_name, gross_amount, gst_amount, net_amount,
                description, category, source_hash, created_from_banking
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, FALSE)
        """, (
            inv['invoice_date'],
            'AMAZON',
            inv['amount'],
            gst_amt,
            net_amt,
            description_tagged,
            '5300',  # Office Equipment/Supplies
            inv['source_hash']
        ))
        
        total_imported += 1
        total_amount += inv['amount']
    
    conn.commit()
    print(f"✅ Created {total_imported} receipts")

else:
    print(f"DRY-RUN: Would create {len(invoices)} receipts\n")
    total_amount = sum(i['amount'] for i in invoices)

print(f"   Total amount: ${total_amount:,.2f}")
print(f"   Date range: {min(i['invoice_date'] for i in invoices)} to {max(i['invoice_date'] for i in invoices)}")
print(f"   Vehicles referenced: {len(set(i['vehicle_ref'] for i in invoices if i['vehicle_ref']))}")

if errors:
    print(f"\n⚠️  Issues ({len(errors)}):")
    for error in errors[:10]:
        print(f"   - {error}")
    if len(errors) > 10:
        print(f"   ... and {len(errors)-10} more")

print("\n" + "="*80)
print("SAMPLE INVOICES (First 10)")
print("="*80 + "\n")

for i, inv in enumerate(invoices[:10], 1):
    date_str = inv['invoice_date'].strftime('%Y-%m-%d')
    amt_str = f"${inv['amount']:>8.2f}"
    veh_str = inv['vehicle_ref'] or 'N/A'
    print(f"{i:2}. {date_str} │ {amt_str} │ {veh_str:<5} │ {inv['description'][:45]}")

print("\n" + "="*80)
if not write_mode:
    print("RUN: python l:\\limo\\scripts\\import_amazon_invoices_full.py --write")
else:
    print("✅ IMPORT COMPLETE")
print("="*80 + "\n")

conn.close()
