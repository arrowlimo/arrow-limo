#!/usr/bin/env python3
"""
Extract IONOS invoices from zip files with amount extraction from PDFs.

Process IONOS website hosting invoice PDFs from downloaded zip archives.
Extract invoice date, amount, and description for accounting records.

Usage:
    python import_ionos_with_amounts.py           # Dry-run
    python import_ionos_with_amounts.py --write   # Apply to database
"""

import os
import sys
import zipfile
import re
import hashlib
from datetime import datetime
from decimal import Decimal
from pathlib import Path
import tempfile

# Add project to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import psycopg2

def get_db_connection():
    """Get PostgreSQL connection."""
    try:
        conn = psycopg2.connect(
            host=os.environ.get('DB_HOST', 'localhost'),
            database=os.environ.get('DB_NAME', 'almsdata'),
            user=os.environ.get('DB_USER', 'postgres'),
            password=os.environ.get('DB_PASSWORD', '***REMOVED***'),
        )
        return conn
    except Exception as e:
        print(f"ERROR: Could not connect to database: {e}")
        sys.exit(1)

def extract_date_from_ionos_filename(filename):
    """
    Extract date from IONOS filename format: 'IN_ 2015-09-29 - 202011542310.pdf'
    Returns YYYY-MM-DD format or None
    """
    try:
        # Pattern: IN_ YYYY-MM-DD - XXXXXX.pdf
        match = re.search(r'IN_\s+(\d{4}-\d{2}-\d{2})', filename)
        if match:
            date_str = match.group(1)
            # Validate it's a real date
            datetime.strptime(date_str, '%Y-%m-%d')
            return date_str
        return None
    except Exception:
        return None

def extract_amount_from_pdf(pdf_content):
    """
    Extract invoice amount from IONOS PDF content.
    Look for common IONOS patterns like "Total" or amounts in EUR/GBP/USD
    
    Returns Decimal amount or None
    """
    try:
        # Convert to text if bytes
        if isinstance(pdf_content, bytes):
            text = pdf_content.decode('utf-8', errors='ignore')
        else:
            text = str(pdf_content)
        
        # Look for total amount - IONOS uses patterns like:
        # "Total: 9.99 EUR" or "Gesamt: 9.99 EUR" or "Total due: USD 9.99"
        
        patterns = [
            r'Total\s*(?:Due|Amount)?[:\s]+(?:EUR|USD|GBP)?\s*([\d,.]+)',
            r'Gesamt[:\s]+(?:EUR|USD|GBP)?\s*([\d,.]+)',
            r'(?:EUR|USD|GBP)\s*([\d,.]+)',
            r'Amount\s*(?:Due)?[:\s]+([\d,.]+)',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                # Take the last (usually most significant) match
                amount_str = matches[-1]
                # Remove spaces and convert comma to dot
                amount_str = amount_str.replace(' ', '').replace(',', '.')
                try:
                    amount = Decimal(amount_str)
                    if amount > 0:
                        return amount
                except:
                    pass
        
        return None
    except Exception as e:
        return None

def load_existing_hashes(conn):
    """Pre-load all existing receipt source hashes."""
    cur = conn.cursor()
    try:
        cur.execute("SELECT source_hash FROM receipts WHERE source_hash IS NOT NULL")
        hashes = {row[0] for row in cur.fetchall()}
        return hashes
    finally:
        cur.close()

def calculate_gst(gross_amount):
    """Calculate GST (5% included in amount)."""
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

def extract_ionos_with_amounts(ionos_dir, write_mode=False):
    """
    Extract IONOS invoices from zip files with amount extraction.
    """
    
    if not os.path.exists(ionos_dir):
        print(f"ERROR: Directory not found: {ionos_dir}")
        sys.exit(1)
    
    print(f"\n{'='*70}")
    print(f"IONOS Invoice Import - {'WRITE MODE' if write_mode else 'DRY-RUN'}")
    print(f"{'='*70}\n")
    
    # Check for PDF libraries
    try:
        import pypdf
        print("✅ PyPDF2 available for PDF extraction\n")
        has_pdf_lib = True
    except:
        print("⚠️  PyPDF2 not available - will use text pattern matching\n")
        has_pdf_lib = False
    
    # Find all zip files
    zip_files = sorted(Path(ionos_dir).glob('IONOS invoices *.zip'))
    
    if not zip_files:
        print(f"ERROR: No IONOS zip files found in {ionos_dir}")
        sys.exit(1)
    
    print(f"Found {len(zip_files)} IONOS zip files\n")
    
    ionos_records = []
    seen_hashes = set()
    extraction_summary = {'total': 0, 'with_amount': 0, 'without_amount': 0, 'errors': 0}
    
    conn = get_db_connection()
    existing_hashes = load_existing_hashes(conn)
    conn.close()
    
    # Extract all invoices from zips
    for zip_idx, zip_path in enumerate(zip_files, 1):
        print(f"[{zip_idx}/{len(zip_files)}] Extracting: {zip_path.name}")
        
        try:
            with zipfile.ZipFile(zip_path, 'r') as zf:
                pdf_files = [f for f in zf.namelist() if f.lower().endswith('.pdf')]
                print(f"     Found {len(pdf_files)} PDF files")
                
                for file_idx, pdf_name in enumerate(pdf_files, 1):
                    try:
                        # Extract date from filename
                        invoice_date = extract_date_from_ionos_filename(pdf_name)
                        
                        if not invoice_date:
                            extraction_summary['errors'] += 1
                            continue
                        
                        # Read PDF content
                        pdf_content = zf.read(pdf_name)
                        
                        # Extract amount from PDF
                        amount = extract_amount_from_pdf(pdf_content)
                        
                        if not amount:
                            # Default to $10/month for IONOS hosting
                            amount = Decimal('10.00')
                            extraction_summary['without_amount'] += 1
                        else:
                            extraction_summary['with_amount'] += 1
                        
                        extraction_summary['total'] += 1
                        
                        vendor_desc = "IONOS Website Hosting"
                        source_hash = generate_source_hash(invoice_date, vendor_desc, amount)
                        
                        # Check duplicates
                        if source_hash in seen_hashes:
                            continue
                        
                        if source_hash in existing_hashes:
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
                            'description': f"IONOS Hosting Invoice: {pdf_name}",
                            'category': 'Marketing/Web Services',
                            'source_hash': source_hash,
                            'created_from_banking': False,
                        }
                        
                        ionos_records.append(record)
                        
                    except Exception as e:
                        extraction_summary['errors'] += 1
                        continue
        
        except Exception as e:
            print(f"  ⚠️  Error reading {zip_path.name}: {e}")
            continue
    
    print(f"\nExtraction Summary:")
    print(f"  Total PDFs processed: {extraction_summary['total']}")
    print(f"  With extracted amounts: {extraction_summary['with_amount']}")
    print(f"  Using default amount: {extraction_summary['without_amount']}")
    print(f"  Errors: {extraction_summary['errors']}")
    
    print(f"\nImport Summary:")
    print(f"  Valid records to import: {len(ionos_records)}")
    
    if len(ionos_records) == 0:
        print(f"\n⚠️  No new records to import!")
        return
    
    # Calculate totals
    total_gross = sum(Decimal(str(r['gross_amount'])) for r in ionos_records)
    total_gst = sum(Decimal(str(r['gst_amount'])) for r in ionos_records)
    total_net = sum(Decimal(str(r['net_amount'])) for r in ionos_records)
    
    print(f"\nFinancial Summary:")
    print(f"  Total Gross Amount: ${total_gross:,.2f}")
    print(f"  Total GST (5%):     ${total_gst:,.2f}")
    print(f"  Total Net Amount:   ${total_net:,.2f}")
    
    # Date range
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
        print(f"   Run with --write flag to apply changes\n")
        return
    
    # Write to database
    print(f"\n{'='*70}")
    print(f"WRITING TO DATABASE...")
    print(f"{'='*70}\n")
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Batch insert
        for rec in ionos_records:
            cur.execute("""
                INSERT INTO receipts
                (receipt_date, vendor_name, gross_amount, gst_amount, net_amount,
                 description, category, source_hash, created_from_banking)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                rec['receipt_date'],
                rec['vendor_name'],
                float(rec['gross_amount']),
                float(rec['gst_amount']),
                float(rec['net_amount']),
                rec['description'],
                rec['category'],
                rec['source_hash'],
                rec['created_from_banking'],
            ))
        
        conn.commit()
        
        print(f"✅ Successfully inserted {len(ionos_records)} IONOS receipts!")
        print(f"   Total amount: ${total_gross:,.2f}")
        
        # Verify
        cur.execute("""
            SELECT COUNT(*), SUM(gross_amount) 
            FROM receipts 
            WHERE vendor_name LIKE 'IONOS%'
        """)
        cnt, amt = cur.fetchone()
        print(f"\nVerification:")
        print(f"  Total IONOS receipts in database: {cnt}")
        print(f"  Total IONOS amount in database: ${amt:,.2f}")
        
    except Exception as e:
        print(f"❌ Database error: {e}")
        conn.rollback()
        sys.exit(1)
    finally:
        cur.close()
        conn.close()
    
    print(f"\n✅ IONOS import completed successfully!")

def main():
    import argparse
    parser = argparse.ArgumentParser(description='Extract IONOS invoices from zip files')
    parser.add_argument('--write', action='store_true', help='Write to database')
    parser.add_argument('--dir', default='l:\\limo\\ionos', help='Path to IONOS folder')
    
    args = parser.parse_args()
    extract_ionos_with_amounts(args.dir, write_mode=args.write)

if __name__ == '__main__':
    main()
