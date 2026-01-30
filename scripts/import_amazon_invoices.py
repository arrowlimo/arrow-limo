#!/usr/bin/env python3
"""
Import Amazon invoices from PDF files into receipts table.
Extracts invoice date, amount, and description from PDF content.
"""
import os
import psycopg2
from pathlib import Path
from datetime import datetime
import re
import hashlib
from PyPDF2 import PdfReader

conn = psycopg2.connect(
    host=os.getenv('DB_HOST', 'localhost'),
    database=os.getenv('DB_NAME', 'almsdata'),
    user=os.getenv('DB_USER', 'postgres'),
    password=os.getenv('DB_PASSWORD', '***REDACTED***'),
)
cur = conn.cursor()

print("\n" + "="*80)
print("AMAZON INVOICE IMPORT - Extract & Create Receipts")
print("="*80 + "\n")

# Get all PDFs
pdf_folder = Path(r"L:\limo\mbna amazon")
pdfs = sorted(pdf_folder.glob("*.pdf"))

invoices = []
errors = []

print(f"Processing {len(pdfs)} PDF files...\n")

for pdf_path in pdfs:
    try:
        pdf = PdfReader(str(pdf_path))
        page = pdf.pages[0]
        text = page.extract_text()
        
        if not text:
            errors.append(f"No text in: {pdf_path.name}")
            continue
        
        # Extract invoice date
        date_match = re.search(r'Invoice date.*?:\s*(\d{1,2})\s+(\w+)\s+(\d{4})', text, re.IGNORECASE)
        if date_match:
            day, month_str, year = date_match.groups()
            try:
                invoice_date = datetime.strptime(f"{day} {month_str} {year}", "%d %B %Y").date()
            except ValueError:
                # Try alternate format
                try:
                    invoice_date = datetime.strptime(f"{day} {month_str} {year}", "%d %b %Y").date()
                except:
                    invoice_date = None
        else:
            invoice_date = None
        
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
        
        # Use filename as description
        description = pdf_path.stem
        
        # Extract vehicle reference from filename or description
        vehicle_match = re.search(r'(L\d{1,2}|E450)', description, re.IGNORECASE)
        vehicle_ref = vehicle_match.group(1) if vehicle_match else None
        
        # Generate hash for duplicate detection
        if invoice_date and amount:
            hash_input = f"amazon|{invoice_date}|{amount:.2f}".encode('utf-8')
            source_hash = hashlib.sha256(hash_input).hexdigest()
        else:
            source_hash = hashlib.sha256(description.encode('utf-8')).hexdigest()
        
        # Check if already exists
        cur.execute("SELECT receipt_id FROM receipts WHERE source_hash = %s", (source_hash,))
        if cur.fetchone():
            errors.append(f"Duplicate (hash match): {pdf_path.name}")
            continue
        
        invoices.append({
            'filename': pdf_path.name,
            'description': description,
            'invoice_date': invoice_date,
            'amount': amount,
            'vehicle_ref': vehicle_ref,
            'source_hash': source_hash,
            'status': 'extracted'
        })
    
    except Exception as e:
        errors.append(f"Error in {pdf_path.name}: {str(e)}")

print(f"✅ Successfully extracted: {len(invoices)} invoices")
if errors:
    print(f"⚠️  Errors/Skipped: {len(errors)}")
    for error in errors[:5]:
        print(f"   - {error}")
    if len(errors) > 5:
        print(f"   ... and {len(errors)-5} more")

print("\n" + "="*80)
print("SAMPLE INVOICES (First 5)")
print("="*80 + "\n")

for i, inv in enumerate(invoices[:5], 1):
    date_str = inv['invoice_date'].strftime('%Y-%m-%d') if inv['invoice_date'] else 'N/A'
    amt_str = f"${inv['amount']:.2f}" if inv['amount'] else "N/A"
    veh_str = inv['vehicle_ref'] or 'N/A'
    print(f"{i}. {date_str} | {amt_str:>10} | {veh_str:<5} | {inv['description'][:40]}")

print("\n" + "="*80)
print(f"READY TO IMPORT: {len(invoices)} invoices")
print("="*80)
print(f"\nThese are David-paid Amazon invoices for vehicle maintenance/repairs")
print(f"Total potential import: {sum(i['amount'] for i in invoices if i['amount'])} (with amounts)")
print(f"\nNext: Run with --write flag to create receipts in database")
print("\n" + "="*80 + "\n")

conn.close()
