#!/usr/bin/env python3
"""
Import Wix billing history CSV to receipts table.

Process Wix billing history export and create receipts with GL categorization.
Handles refunds and duplicate detection via source hash.

Usage:
    python import_wix_receipts.py           # Dry-run (show what would be imported)
    python import_wix_receipts.py --write   # Apply to database
"""

import os
import sys
import csv
import hashlib
import argparse
from datetime import datetime
from decimal import Decimal

# Add project to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import psycopg2
from psycopg2.extras import execute_values
import psycopg2.errors

# Database connection
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

def parse_date(date_str):
    """Parse Wix date format 'Oct 31 2025' to 'YYYY-MM-DD'."""
    if not date_str or date_str.strip() == '':
        return None
    
    try:
        # Parse formats like "Oct 31 2025" or "May 27 2025"
        dt = datetime.strptime(date_str.strip(), "%b %d %Y")
        return dt.strftime("%Y-%m-%d")
    except ValueError as e:
        print(f"WARNING: Could not parse date '{date_str}': {e}")
        return None

def parse_amount(amount_str):
    """Parse Wix amount format '$62.84' or 'CA$166.87' to Decimal."""
    if not amount_str or amount_str.strip() == '':
        return None
    
    try:
        # Remove currency symbols and whitespace
        cleaned = amount_str.strip().replace('CA$', '').replace('$', '').strip()
        
        # Handle negative amounts (refunds)
        return Decimal(cleaned)
    except Exception as e:
        print(f"WARNING: Could not parse amount '{amount_str}': {e}")
        return None

def generate_source_hash(invoice_date, description, amount):
    """Generate SHA256 hash for deduplication."""
    if not invoice_date or not amount:
        return None
    
    hash_input = f"{invoice_date}|{description}|{float(amount):.2f}".encode('utf-8')
    return hashlib.sha256(hash_input).hexdigest()

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
    
    # GST is included in total: gst = total * (0.05 / 1.05)
    gst_amount = gross_amount * Decimal('0.05') / Decimal('1.05')
    net_amount = gross_amount - gst_amount
    
    return round(gst_amount, 2), round(net_amount, 2)

def map_subscription_to_category(subscription, description):
    """Map Wix subscription type to GL category description."""
    sub_lower = subscription.lower() if subscription else ""
    desc_lower = description.lower() if description else ""
    
    if 'domain' in sub_lower:
        return 'Wix Domain'
    elif 'premium plan' in sub_lower or 'unlimited' in desc_lower:
        return 'Wix Premium Plan'
    elif 'g suite' in sub_lower or 'mailbox' in desc_lower:
        return 'Wix G Suite Mailbox'
    elif 'tpa' in sub_lower or 'site booster' in desc_lower:
        return 'Wix Site Booster'
    else:
        return f'Wix {subscription}'

def import_wix_receipts(csv_file, write_mode=False):
    """
    Import Wix billing history CSV to receipts table.
    
    Args:
        csv_file: Path to Wix CSV file
        write_mode: If True, write to database; if False, dry-run only
    """
    
    if not os.path.exists(csv_file):
        print(f"ERROR: File not found: {csv_file}")
        sys.exit(1)
    
    print(f"\n{'='*70}")
    print(f"Wix Billing History Import - {'WRITE MODE' if write_mode else 'DRY-RUN'}")
    print(f"{'='*70}\n")
    
    conn = None
    
    try:
        # Connect to database
        conn = get_db_connection()
        
        # Pre-load existing hashes
        existing_hashes = load_existing_hashes(conn)
        
        # Parse CSV
        wix_records = []
        duplicates_in_file = []
        seen_hashes = set()  # Track duplicates within THIS import file
        
        print(f"\nReading CSV from: {csv_file}\n")
        
        with open(csv_file, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            
            for row_idx, row in enumerate(reader, start=2):  # Start at 2 (header is 1)
                try:
                    invoice_number = row.get('Invoice Number', '').strip()
                    invoice_date = row.get('Date', '').strip()
                    subscription = row.get('Subscription', '').strip()
                    description = row.get('Description', '').strip()
                    site_name = row.get('Site Name', '').strip()
                    payment_method = row.get('Payment Method', '').strip()
                    amount_str = row.get('Amount', '').strip()
                    status = row.get('Status', '').strip()
                    
                    # Parse date and amount
                    parsed_date = parse_date(invoice_date)
                    parsed_amount = parse_amount(amount_str)
                    
                    if not parsed_date:
                        print(f"  ⚠️  Row {row_idx}: Skipped - Could not parse date '{invoice_date}'")
                        continue
                    
                    if not parsed_amount:
                        print(f"  ⚠️  Row {row_idx}: Skipped - Could not parse amount '{amount_str}'")
                        continue
                    
                    # Skip refunds (negative amounts)
                    if parsed_amount < 0:
                        print(f"  ⚠️  Row {row_idx}: Skipped refund - {invoice_number} {subscription} {parsed_amount}")
                        continue
                    
                    # Generate vendor description
                    vendor_desc = f"Wix - {subscription} ({site_name})" if site_name else f"Wix - {subscription}"
                    category_desc = map_subscription_to_category(subscription, description)
                    
                    # Generate source hash
                    source_hash = generate_source_hash(parsed_date, vendor_desc, parsed_amount)
                    
                    # Check for duplicates within THIS CSV file
                    if source_hash in seen_hashes:
                        print(f"  ⚠️  Row {row_idx}: Duplicate within file - {invoice_number} {vendor_desc} ${parsed_amount}")
                        duplicates_in_file.append({
                            'invoice_number': invoice_number,
                            'date': parsed_date,
                            'vendor': vendor_desc,
                            'amount': parsed_amount,
                            'reason': 'Duplicate within CSV file'
                        })
                        continue
                    
                    seen_hashes.add(source_hash)
                    
                    # Check for duplicates in existing database
                    if source_hash in existing_hashes:
                        print(f"  ℹ️  Row {row_idx}: Duplicate (hash exists) - {invoice_number} {vendor_desc} ${parsed_amount}")
                        duplicates_in_file.append({
                            'invoice_number': invoice_number,
                            'date': parsed_date,
                            'vendor': vendor_desc,
                            'amount': parsed_amount,
                            'reason': 'Hash exists in database'
                        })
                        continue
                    
                    # Calculate GST
                    gst_amount, net_amount = calculate_gst(parsed_amount)
                    
                    # Build record
                    record = {
                        'receipt_date': parsed_date,
                        'vendor_name': vendor_desc,
                        'gross_amount': parsed_amount,
                        'gst_amount': gst_amount,
                        'net_amount': net_amount,
                        'description': f"Wix Invoice {invoice_number}: {description}",
                        'category': 'Marketing/Web Services',  # GL 5450
                        'payment_method': payment_method,
                        'source_hash': source_hash,
                        'created_from_banking': False,
                        'invoice_number': invoice_number,
                        'subscription_type': subscription,
                    }
                    
                    wix_records.append(record)
                    
                except Exception as e:
                    print(f"  ❌ Row {row_idx}: Error processing - {e}")
                    continue
        
        print(f"\nProcessing Summary:")
        print(f"  Total records read: {row_idx - 1}")
        print(f"  Valid records to import: {len(wix_records)}")
        print(f"  Duplicates skipped: {len(duplicates_in_file)}")
        print(f"  Total refunds skipped: (counted above)")
        
        if duplicates_in_file:
            print(f"\nDuplicate Records Skipped:")
            for dup in duplicates_in_file:
                print(f"  - {dup['invoice_number']} ({dup['date']}) {dup['vendor']} ${dup['amount']}")
        
        if len(wix_records) == 0:
            print(f"\n⚠️  No new records to import!")
            return
        
        # Calculate totals
        total_gross = sum(Decimal(str(r['gross_amount'])) for r in wix_records)
        total_gst = sum(Decimal(str(r['gst_amount'])) for r in wix_records)
        total_net = sum(Decimal(str(r['net_amount'])) for r in wix_records)
        
        print(f"\nFinancial Summary:")
        print(f"  Total Gross Amount: ${total_gross:,.2f}")
        print(f"  Total GST (5%):     ${total_gst:,.2f}")
        print(f"  Total Net Amount:   ${total_net:,.2f}")
        
        # Show date range
        dates = [r['receipt_date'] for r in wix_records]
        if dates:
            print(f"\nDate Range:")
            print(f"  Earliest: {min(dates)}")
            print(f"  Latest:   {max(dates)}")
        
        # Preview first few records
        print(f"\nPreview (first 5 records):")
        for i, rec in enumerate(wix_records[:5], 1):
            print(f"  {i}. {rec['receipt_date']} {rec['vendor_name']} ${rec['gross_amount']}")
        
        if len(wix_records) > 5:
            print(f"  ... and {len(wix_records) - 5} more records")
        
        if not write_mode:
            print(f"\n⚠️  DRY-RUN MODE: No database changes made")
            print(f"   Run with --write flag to apply changes\n")
            return
        
        # Write to database
        print(f"\n{'='*70}")
        print(f"WRITING TO DATABASE...")
        print(f"{'='*70}\n")
        
        cur = conn.cursor()
        
        try:
            # Build insert records as dictionaries for executemany
            insert_records = []
            for rec in wix_records:
                insert_records.append({
                    'receipt_date': rec['receipt_date'],
                    'vendor_name': rec['vendor_name'],
                    'gross_amount': float(rec['gross_amount']),
                    'gst_amount': float(rec['gst_amount']),
                    'net_amount': float(rec['net_amount']),
                    'description': rec['description'],
                    'category': rec['category'],
                    'source_hash': rec['source_hash'],
                    'created_from_banking': rec['created_from_banking'],
                })
            
            # Execute batch insert using psycopg2 executemany
            cur.executemany(
                """
                INSERT INTO receipts 
                (receipt_date, vendor_name, gross_amount, gst_amount, net_amount, 
                 description, category, source_hash, created_from_banking)
                VALUES (%(receipt_date)s, %(vendor_name)s, %(gross_amount)s, %(gst_amount)s, 
                        %(net_amount)s, %(description)s, %(category)s, %(source_hash)s, 
                        %(created_from_banking)s)
                """,
                insert_records
            )
            
            inserted_count = cur.rowcount
            
            conn.commit()
            
            print(f"✅ Successfully inserted {inserted_count} Wix receipts!")
            print(f"   Total amount: ${total_gross:,.2f}")
            
            # Verify insertion
            cur.execute(
                "SELECT COUNT(*), SUM(gross_amount) FROM receipts WHERE vendor_name LIKE 'Wix%'"
            )
            wix_count, wix_total = cur.fetchone()
            print(f"\nVerification:")
            print(f"  Total Wix receipts in database: {wix_count:,}")
            print(f"  Total Wix amount in database: ${wix_total:,.2f}")
            
        except psycopg2.errors.UniqueViolation as e:
            print(f"❌ Database error (duplicate key): {e}")
            conn.rollback()
            sys.exit(1)
        except Exception as e:
            print(f"❌ Database error: {e}")
            conn.rollback()
            sys.exit(1)
        finally:
            cur.close()
        
        print(f"\n✅ Wix import completed successfully!")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        if conn:
            conn.close()

def main():
    parser = argparse.ArgumentParser(description='Import Wix billing history to receipts table')
    parser.add_argument('--write', action='store_true', help='Write to database (default is dry-run)')
    parser.add_argument('--csv', default='l:\\limo\\wix\\billing_history_Dec_06_2025 (1).csv', 
                       help='Path to Wix CSV file')
    
    args = parser.parse_args()
    
    import_wix_receipts(args.csv, write_mode=args.write)

if __name__ == '__main__':
    main()
