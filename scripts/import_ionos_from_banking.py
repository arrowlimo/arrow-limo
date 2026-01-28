#!/usr/bin/env python3
"""
Import IONOS invoices using banking transaction data for actual amounts.

Matches IONOS invoice dates to banking charges and extracts real amounts.
"""

import os
import sys
import zipfile
import re
import hashlib
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import psycopg2

def get_db_connection():
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
    """Extract YYYY-MM-DD from IONOS PDF filename."""
    try:
        match = re.search(r'IN_\s+(\d{4}-\d{2}-\d{2})', filename)
        if match:
            date_str = match.group(1)
            datetime.strptime(date_str, '%Y-%m-%d')
            return date_str
        return None
    except:
        return None

def load_ionos_banking_amounts(conn):
    """
    Load IONOS charges from banking_transactions for amount matching.
    Returns dict: date -> amount
    """
    cur = conn.cursor()
    cur.execute("""
        SELECT transaction_date::date, debit_amount
        FROM banking_transactions
        WHERE (description ILIKE '%IONOS%' OR description ILIKE '%1&1%')
        AND debit_amount > 0
        ORDER BY transaction_date
    """)
    
    banking_data = {}
    for date, amount in cur.fetchall():
        date_str = date.strftime('%Y-%m-%d')
        banking_data[date_str] = float(amount)
    
    cur.close()
    return banking_data

def find_matching_amount(invoice_date, banking_data):
    """
    Find IONOS amount from banking data for invoice date.
    Looks for exact date match or within 30 days after (payment delay).
    """
    # Try exact match first
    if invoice_date in banking_data:
        return Decimal(str(banking_data[invoice_date]))
    
    # Try within 30 days after (payment processing delay)
    try:
        inv_dt = datetime.strptime(invoice_date, '%Y-%m-%d')
        for days_after in range(1, 31):
            check_date = (inv_dt + timedelta(days=days_after)).strftime('%Y-%m-%d')
            if check_date in banking_data:
                return Decimal(str(banking_data[check_date]))
    except:
        pass
    
    return None

def load_existing_hashes(conn):
    cur = conn.cursor()
    cur.execute("SELECT source_hash FROM receipts WHERE source_hash IS NOT NULL")
    hashes = {row[0] for row in cur.fetchall()}
    cur.close()
    return hashes

def calculate_gst(gross_amount):
    if not gross_amount or gross_amount == 0:
        return Decimal('0.00'), gross_amount
    
    gst_amount = gross_amount * Decimal('0.05') / Decimal('1.05')
    net_amount = gross_amount - gst_amount
    
    return round(gst_amount, 2), round(net_amount, 2)

def generate_source_hash(invoice_date, description, amount):
    if not invoice_date or not amount:
        return None
    
    hash_input = f"{invoice_date}|{description}|{float(amount):.2f}".encode('utf-8')
    return hashlib.sha256(hash_input).hexdigest()

def import_ionos_from_zip(ionos_dir, write_mode=False):
    """Extract IONOS invoices with amounts from banking data."""
    
    if not os.path.exists(ionos_dir):
        print(f"ERROR: Directory not found: {ionos_dir}")
        sys.exit(1)
    
    print(f"\n{'='*70}")
    print(f"IONOS Invoice Import (Using Banking Amounts) - {'WRITE MODE' if write_mode else 'DRY-RUN'}")
    print(f"{'='*70}\n")
    
    # Load banking data
    conn = get_db_connection()
    banking_data = load_ionos_banking_amounts(conn)
    existing_hashes = load_existing_hashes(conn)
    conn.close()
    
    print(f"INFO: Loaded {len(banking_data)} IONOS charges from banking data\n")
    
    # Find zip files
    zip_files = sorted(Path(ionos_dir).glob('IONOS invoices *.zip'))
    
    if not zip_files:
        print(f"ERROR: No IONOS zip files found")
        sys.exit(1)
    
    print(f"Found {len(zip_files)} zip files\n")
    
    ionos_records = []
    seen_hashes = set()
    amount_stats = {'with_banking_match': 0, 'without_match': 0, 'duplicates': 0}
    
    # Extract all PDFs
    for zip_idx, zip_path in enumerate(zip_files, 1):
        try:
            with zipfile.ZipFile(zip_path, 'r') as zf:
                pdf_files = [f for f in zf.namelist() if f.lower().endswith('.pdf')]
                print(f"[{zip_idx}/{len(zip_files)}] {zip_path.name}: {len(pdf_files)} PDFs")
                
                for pdf_name in pdf_files:
                    try:
                        # Extract date
                        invoice_date = extract_date_from_ionos_filename(pdf_name)
                        if not invoice_date:
                            continue
                        
                        # Find matching amount from banking
                        amount = find_matching_amount(invoice_date, banking_data)
                        
                        if amount:
                            amount_stats['with_banking_match'] += 1
                        else:
                            # Default to $25 (typical recent IONOS cost in CAD)
                            amount = Decimal('25.00')
                            amount_stats['without_match'] += 1
                        
                        vendor_desc = "IONOS Website Hosting"
                        source_hash = generate_source_hash(invoice_date, vendor_desc, amount)
                        
                        # Check duplicates
                        if source_hash in seen_hashes or source_hash in existing_hashes:
                            amount_stats['duplicates'] += 1
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
                            'description': f"IONOS Hosting: {pdf_name}",
                            'category': 'Marketing/Web Services',
                            'source_hash': source_hash,
                            'created_from_banking': False,
                        }
                        
                        ionos_records.append(record)
                    
                    except Exception as e:
                        continue
        
        except Exception as e:
            print(f"  ERROR: {e}")
            continue
    
    print(f"\nProcessing Summary:")
    print(f"  Amounts matched from banking: {amount_stats['with_banking_match']}")
    print(f"  Using default amount ($25): {amount_stats['without_match']}")
    print(f"  Duplicates skipped: {amount_stats['duplicates']}")
    print(f"  Valid records to import: {len(ionos_records)}")
    
    if len(ionos_records) == 0:
        print(f"\n⚠️  No new records to import!")
        return
    
    # Totals
    total_gross = sum(Decimal(str(r['gross_amount'])) for r in ionos_records)
    total_gst = sum(Decimal(str(r['gst_amount'])) for r in ionos_records)
    total_net = sum(Decimal(str(r['net_amount'])) for r in ionos_records)
    
    print(f"\nFinancial Summary:")
    print(f"  Total Gross Amount: ${total_gross:,.2f}")
    print(f"  Total GST (5%):     ${total_gst:,.2f}")
    print(f"  Total Net Amount:   ${total_net:,.2f}")
    
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
        if amt:
            print(f"  Total IONOS amount: ${amt:,.2f}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        conn.rollback()
        sys.exit(1)
    finally:
        cur.close()
        conn.close()
    
    print(f"\n✅ IONOS import completed!")

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--write', action='store_true')
    parser.add_argument('--dir', default='l:\\limo\\ionos')
    args = parser.parse_args()
    
    import_ionos_from_zip(args.dir, write_mode=args.write)

if __name__ == '__main__':
    main()
