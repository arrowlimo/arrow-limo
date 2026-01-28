#!/usr/bin/env python3
"""
Extract IONOS invoices from zip files and import to receipts table.

Process IONOS website hosting invoice PDFs from downloaded zip archives.
Extract invoice date, amount, and description for accounting records.

Usage:
    python import_ionos_invoices.py           # Dry-run (show what would be imported)
    python import_ionos_invoices.py --write   # Apply to database
"""

import os
import sys
import zipfile
import re
import hashlib
from datetime import datetime
from decimal import Decimal
from pathlib import Path

# Add project to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import psycopg2
from psycopg2.extras import execute_values

def get_db_connection():
    """Get PostgreSQL connection from environment variables."""
    try:
        conn = psycopg2.connect(
            host=os.environ.get('DB_HOST', 'localhost'),
            database=os.environ.get('DB_NAME', 'almsdata'),
            user=os.environ.get('DB_USER', 'postgres'),
            password=os.environ.get('DB_PASSWORD', '***REMOVED***'),
            port=os.environ.get('DB_PORT', '5432')
        )
        return conn
    except Exception as e:
        print(f"ERROR: Could not connect to database: {e}")
        sys.exit(1)

def extract_invoice_data_from_pdf_filename(filename):
    """
    Extract invoice information from IONOS PDF filename format.
    
    Expected format: IONOS_HOSTING_invoice_20170710_000001.pdf
    Returns: (date_str, invoice_number, description) or None
    """
    try:
        # Pattern: invoice_YYYYMMDD_XXXXXX
        match = re.search(r'invoice_(\d{8})_(\d+)', filename, re.IGNORECASE)
        if match:
            date_str = match.group(1)
            invoice_num = match.group(2)
            
            # Parse YYYYMMDD to YYYY-MM-DD
            year = date_str[0:4]
            month = date_str[4:6]
            day = date_str[6:8]
            
            parsed_date = f"{year}-{month}-{day}"
            
            return parsed_date, invoice_num, f"IONOS Invoice {invoice_num}"
        
        return None
    except Exception as e:
        print(f"  ⚠️  Could not parse filename '{filename}': {e}")
        return None

def get_ionos_amount_from_filename(filename, zip_path):
    """
    Try to extract invoice amount from IONOS PDF or filename.
    
    For now, we'll use filename patterns. 
    IONOS typically names files with invoice info but amount may need extraction from PDF content.
    """
    # Try to detect amount from common IONOS invoice patterns
    # For now, return None and we'll handle this separately
    return None

def load_existing_hashes(conn):
    """Pre-load all existing receipt source hashes into memory set."""
    cur = conn.cursor()
    try:
        cur.execute("SELECT source_hash FROM receipts WHERE source_hash IS NOT NULL")
        hashes = {row[0] for row in cur.fetchall()}
        print(f"INFO: Pre-loaded {len(hashes):,} existing receipt hashes from database")
        return hashes
    finally:
        cur.close()

def calculate_gst(gross_amount):
    """Calculate GST (5% included in amount for Alberta)."""
    if not gross_amount or gross_amount == 0:
        return Decimal('0.00'), gross_amount
    
    gst_amount = gross_amount * Decimal('0.05') / Decimal('1.05')
    net_amount = gross_amount - gst_amount
    
    return round(gst_amount, 2), round(net_amount, 2)

def generate_source_hash(invoice_date, description, amount):
    """Generate SHA256 hash for deduplication."""
    if not invoice_date or not amount:
        return None
    
    hash_input = f"{invoice_date}|{description}|{float(amount):.2f}".encode('utf-8')
    return hashlib.sha256(hash_input).hexdigest()

def extract_ionos_invoices(ionos_dir, write_mode=False):
    """
    Extract IONOS invoices from zip files and prepare for import.
    
    Args:
        ionos_dir: Path to IONOS folder containing zip files
        write_mode: If True, write to database; if False, dry-run only
    """
    
    if not os.path.exists(ionos_dir):
        print(f"ERROR: Directory not found: {ionos_dir}")
        sys.exit(1)
    
    print(f"\n{'='*70}")
    print(f"IONOS Invoice Import - {'WRITE MODE' if write_mode else 'DRY-RUN'}")
    print(f"{'='*70}\n")
    
    # Find all zip files
    zip_files = sorted(Path(ionos_dir).glob('IONOS invoices *.zip'))
    
    if not zip_files:
        print(f"ERROR: No IONOS zip files found in {ionos_dir}")
        sys.exit(1)
    
    print(f"Found {len(zip_files)} IONOS zip files\n")
    
    ionos_records = []
    duplicates_found = []
    invoice_files = []
    
    # Extract all invoice files from zips
    for zip_path in zip_files:
        print(f"Extracting: {zip_path.name}")
        
        try:
            with zipfile.ZipFile(zip_path, 'r') as zf:
                for file_info in zf.filelist:
                    if file_info.filename.lower().endswith('.pdf'):
                        invoice_files.append({
                            'zip_file': zip_path.name,
                            'pdf_file': file_info.filename,
                            'size': file_info.file_size
                        })
        except Exception as e:
            print(f"  ⚠️  Error reading {zip_path.name}: {e}")
            continue
    
    print(f"\nFound {len(invoice_files)} invoice PDF files in zip archives\n")
    
    # Parse invoice filenames
    print("Processing invoice files:\n")
    
    conn = get_db_connection()
    existing_hashes = load_existing_hashes(conn)
    conn.close()
    
    seen_hashes = set()
    
    for i, invoice in enumerate(invoice_files, 1):
        pdf_name = Path(invoice['pdf_file']).name
        
        # Try to extract invoice data from filename
        parsed = extract_invoice_data_from_pdf_filename(pdf_name)
        
        if not parsed:
            print(f"  ⚠️  Row {i}: Could not parse filename '{pdf_name}'")
            continue
        
        invoice_date, invoice_num, description = parsed
        
        # For IONOS, we need to estimate amounts based on typical hosting costs
        # Standard IONOS website hosting is typically ~$10-15/month
        # Without parsing PDFs, we'll note this limitation
        
        # Try to extract amount from filename if present
        # IONOS filenames might contain pricing info
        amount = None
        
        # Look for amount patterns in filename (e.g., "50_00" for 50.00)
        amount_match = re.search(r'(\d+)[_-]?(\d{2})', pdf_name)
        if amount_match:
            amount = Decimal(f"{amount_match.group(1)}.{amount_match.group(2)}")
        
        if not amount:
            # Default IONOS hosting estimate: $10/month
            # This is a placeholder - real amounts would need PDF parsing
            print(f"  ℹ️  Row {i}: Amount not in filename - using placeholder for {invoice_date}")
            amount = Decimal('10.00')  # Placeholder
        
        vendor_desc = f"IONOS Website Hosting"
        source_hash = generate_source_hash(invoice_date, vendor_desc, amount)
        
        # Check for duplicates
        if source_hash in seen_hashes:
            print(f"  ⚠️  Row {i}: Duplicate within file - {invoice_date} {vendor_desc} ${amount}")
            duplicates_found.append({
                'invoice_number': invoice_num,
                'date': invoice_date,
                'vendor': vendor_desc,
                'amount': amount
            })
            continue
        
        if source_hash in existing_hashes:
            print(f"  ℹ️  Row {i}: Already in database - {invoice_date} {vendor_desc} ${amount}")
            continue
        
        seen_hashes.add(source_hash)
        
        # Calculate GST
        gst_amount, net_amount = calculate_gst(amount)
        
        # Build record
        record = {
            'receipt_date': invoice_date,
            'vendor_name': vendor_desc,
            'gross_amount': amount,
            'gst_amount': gst_amount,
            'net_amount': net_amount,
            'description': f"IONOS Invoice {invoice_num}: {invoice['pdf_file']}",
            'category': 'Marketing/Web Services',  # GL 5450
            'source_hash': source_hash,
            'created_from_banking': False,
            'invoice_number': invoice_num,
        }
        
        ionos_records.append(record)
        print(f"  ✅ Row {i}: {invoice_date} {vendor_desc} ${amount}")
    
    print(f"\nProcessing Summary:")
    print(f"  Total invoice files: {len(invoice_files)}")
    print(f"  Valid records to import: {len(ionos_records)}")
    print(f"  Duplicates skipped: {len(duplicates_found)}")
    print(f"  Already in database: {len(invoice_files) - len(ionos_records) - len(duplicates_found)}")
    
    if len(ionos_records) == 0:
        print(f"\n⚠️  No new records to import!")
        print(f"NOTE: IONOS PDF parsing requires OCR/PDF content extraction.")
        print(f"      Current implementation extracts dates from filenames only.")
        print(f"      To import with actual amounts, you need to either:")
        print(f"      1. Extract PDF content with pdfplumber or PyPDF2")
        print(f"      2. Manually enter amounts from invoices")
        print(f"      3. Estimate based on invoice history patterns")
        return
    
    # Calculate totals
    total_gross = sum(Decimal(str(r['gross_amount'])) for r in ionos_records)
    total_gst = sum(Decimal(str(r['gst_amount'])) for r in ionos_records)
    total_net = sum(Decimal(str(r['net_amount'])) for r in ionos_records)
    
    print(f"\nFinancial Summary (using available data):")
    print(f"  Total Gross Amount: ${total_gross:,.2f}")
    print(f"  Total GST (5%):     ${total_gst:,.2f}")
    print(f"  Total Net Amount:   ${total_net:,.2f}")
    
    # Show date range
    dates = [r['receipt_date'] for r in ionos_records]
    if dates:
        print(f"\nDate Range:")
        print(f"  Earliest: {min(dates)}")
        print(f"  Latest:   {max(dates)}")
    
    print(f"\nPreview (first 5 records):")
    for i, rec in enumerate(ionos_records[:5], 1):
        print(f"  {i}. {rec['receipt_date']} {rec['vendor_name']} ${rec['gross_amount']}")
    
    if len(ionos_records) > 5:
        print(f"  ... and {len(ionos_records) - 5} more records")
    
    if not write_mode:
        print(f"\n⚠️  DRY-RUN MODE: No database changes made")
        print(f"   Run with --write flag to apply changes")
        print(f"\nNOTE: Amounts are placeholder values.")
        print(f"      Update with actual IONOS invoice amounts before final import.")
        return
    
    # Write to database (placeholder implementation)
    print(f"\n{'='*70}")
    print(f"IMPORTANT: ACTUAL AMOUNTS NEEDED")
    print(f"{'='*70}")
    print(f"\nIONOS invoice PDFs found but amounts not extracted.")
    print(f"Next steps:")
    print(f"1. Manually extract amounts from IONOS PDF invoices")
    print(f"2. Create CSV with: date, invoice_number, amount")
    print(f"3. Run import_ionos_invoices_with_amounts.py to import with real data")

def main():
    import argparse
    parser = argparse.ArgumentParser(description='Extract IONOS invoices from zip files')
    parser.add_argument('--write', action='store_true', help='Write to database (default is dry-run)')
    parser.add_argument('--dir', default='l:\\limo\\ionos', help='Path to IONOS folder')
    
    args = parser.parse_args()
    
    extract_ionos_invoices(args.dir, write_mode=args.write)

if __name__ == '__main__':
    main()
