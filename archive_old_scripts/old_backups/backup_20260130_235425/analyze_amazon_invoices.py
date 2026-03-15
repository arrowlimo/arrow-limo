#!/usr/bin/env python3
"""
Process Amazon invoice PDFs from L:\limo\mbna amazon\ folder.
Extract invoice information from filenames and create receipts.
"""
import os
import psycopg2
from pathlib import Path
from datetime import datetime
import hashlib
import re

conn = psycopg2.connect(
    host=os.getenv('DB_HOST', 'localhost'),
    database=os.getenv('DB_NAME', 'almsdata'),
    user=os.getenv('DB_USER', 'postgres'),
    password=os.getenv('DB_PASSWORD', '***REDACTED***'),
)
cur = conn.cursor()

print("\n" + "="*80)
print("AMAZON INVOICE IMPORT - PDF Filename Analysis")
print("="*80 + "\n")

# Get all PDFs in the folder
pdf_folder = Path(r"L:\limo\mbna amazon")
pdfs = sorted(pdf_folder.glob("*.pdf"))

print(f"Found {len(pdfs)} PDF files\n")

# Parse filename to extract item description and vehicle reference
invoices = []
vehicle_refs = set()

for pdf_path in pdfs:
    filename = pdf_path.stem  # Remove .pdf extension
    
    # Extract vehicle references (L8, L10, L11, L18, L19, L22, L23, E450)
    vehicle_match = re.search(r'(L\d{1,2}|E450)', filename, re.IGNORECASE)
    vehicle_ref = vehicle_match.group(1) if vehicle_match else None
    
    if vehicle_ref:
        vehicle_refs.add(vehicle_ref)
    
    invoices.append({
        'filename': filename,
        'pdf_path': str(pdf_path),
        'vehicle_ref': vehicle_ref,
        'file_size': pdf_path.stat().st_size,
        'file_date': datetime.fromtimestamp(pdf_path.stat().st_mtime)
    })

print("Vehicle References Found:")
for vehicle in sorted(vehicle_refs):
    count = sum(1 for i in invoices if i['vehicle_ref'] == vehicle)
    print(f"  {vehicle}: {count} invoices")

print(f"\nNo Vehicle Reference: {sum(1 for i in invoices if not i['vehicle_ref'])} invoices")

print("\n" + "="*80)
print("SAMPLE INVOICES (First 10)")
print("="*80 + "\n")

for i, inv in enumerate(invoices[:10], 1):
    print(f"{i:2}. {inv['filename']:<50} Vehicle: {inv['vehicle_ref'] or 'N/A':<5} ({inv['file_date'].strftime('%Y-%m-%d')})")

print("\n" + "="*80)
print("ANALYSIS COMPLETE")
print("="*80)
print(f"\nTotal invoices: {len(invoices)}")
print(f"Unique vehicles: {len(vehicle_refs)}")
print(f"\nNext: Create receipts table entries from these invoices")
print(f"Note: File modification dates will be used as receipt_date")
print(f"Note: 'AMAZON' will be vendor_name")
print(f"Note: Need to extract amounts from PDF content (currently unavailable)")
print("\n" + "="*80 + "\n")

conn.close()
