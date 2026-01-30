#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Import GoDaddy receipts from CSV to database.
Creates receipt records with proper GL categorization for web hosting/domains.
"""

import os
import csv
import sys
import hashlib
from datetime import datetime
import psycopg2
from psycopg2.extras import execute_values

# Database connection
def get_db_connection():
    conn = psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REDACTED***')
    )
    return conn

# GL Categories for web hosting/domain services
GL_CATEGORIES = {
    'Websites + Marketing': 5450,      # Marketing/Advertising
    'Domain': 5450,                    # Marketing/Advertising (domain registration)
    'SSL': 5450,                       # Web hosting security
    'Hosting': 5450,                   # Web hosting
    'SiteLock': 5450,                  # Web hosting security
    'GoCentral': 5450,                 # Website builder/hosting
}

def get_gl_code(product_name):
    """Determine GL code based on product name."""
    if not product_name:
        return 5450  # Default to marketing
    
    product_lower = product_name.lower()
    
    for keyword, gl_code in GL_CATEGORIES.items():
        if keyword.lower() in product_lower:
            return gl_code
    
    return 5450  # Default

def generate_hash(date_str, vendor, amount):
    """Generate SHA256 hash for duplicate detection."""
    hash_input = f"{date_str}|{vendor}|{amount:.2f}".encode('utf-8')
    return hashlib.sha256(hash_input).hexdigest()

def import_godaddy_receipts(csv_file, write=False, dry_run=True):
    """Import GoDaddy receipts from CSV."""
    
    if not os.path.exists(csv_file):
        print(f"❌ File not found: {csv_file}")
        return False
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Get existing receipt hashes
        cur.execute("SELECT source_hash FROM receipts WHERE source_hash IS NOT NULL")
        existing_hashes = {row[0] for row in cur.fetchall()}
        print(f"✅ Loaded {len(existing_hashes)} existing receipt hashes")
        
        # Read and process CSV
        receipts_to_import = []
        duplicates = 0
        
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            
            for row in reader:
                try:
                    # Parse data
                    receipt_date = datetime.fromisoformat(row['Order date'].replace('Z', '+00:00')).date()
                    product_name = row.get('Product name', 'GoDaddy Service')
                    vendor_name = 'GoDaddy'
                    gross_amount = float(row.get('Order total', 0))
                    tax_amount = float(row.get('Tax amount', 0))
                    net_amount = gross_amount - tax_amount
                    
                    # Skip $0 transactions
                    if gross_amount == 0:
                        continue
                    
                    # Generate hash
                    source_hash = generate_hash(str(receipt_date), vendor_name, gross_amount)
                    
                    # Check for duplicates
                    if source_hash in existing_hashes:
                        duplicates += 1
                        continue
                    
                    # Get GL code
                    gl_code = get_gl_code(product_name)
                    
                    # Determine category name
                    if 'domain' in product_name.lower():
                        category = 'web_domain'
                    elif 'hosting' in product_name.lower():
                        category = 'web_hosting'
                    elif 'ssl' in product_name.lower():
                        category = 'web_ssl'
                    else:
                        category = 'web_other'
                    
                    receipts_to_import.append({
                        'receipt_date': receipt_date,
                        'vendor_name': vendor_name,
                        'gross_amount': gross_amount,
                        'gst_amount': tax_amount,
                        'net_amount': net_amount,
                        'description': product_name,
                        'category': category,
                        'gl_code': gl_code,
                        'source_hash': source_hash,
                        'created_from_godaddy': True
                    })
                    
                    existing_hashes.add(source_hash)
                    
                except Exception as e:
                    print(f"⚠️ Error processing row: {e}")
                    continue
        
        print(f"\n📊 IMPORT SUMMARY:")
        print(f"   Total to import: {len(receipts_to_import)}")
        print(f"   Duplicates skipped: {duplicates}")
        print(f"   New receipts: {len(receipts_to_import)}")
        
        if not receipts_to_import:
            print("❌ No new receipts to import")
            return False
        
        # Show sample
        print(f"\n📋 SAMPLE RECEIPTS (first 5):")
        for i, receipt in enumerate(receipts_to_import[:5], 1):
            print(f"   {i}. {receipt['receipt_date']} | {receipt['vendor_name']} | ${receipt['gross_amount']:.2f} | {receipt['description'][:40]}")
        
        if dry_run:
            print(f"\n✅ DRY RUN COMPLETE - {len(receipts_to_import)} receipts ready to import")
            print("   Run with --write flag to apply changes")
            conn.close()
            return True
        
        if not write:
            print(f"\n✅ DRY RUN COMPLETE - {len(receipts_to_import)} receipts ready to import")
            print("   Run with --write flag to apply changes")
            conn.close()
            return True
        
        # Insert receipts
        print(f"\n💾 IMPORTING {len(receipts_to_import)} RECEIPTS...")
        
        insert_query = """
            INSERT INTO receipts (
                receipt_date, vendor_name, gross_amount, gst_amount, net_amount,
                description, category, created_from_banking, source_hash
            ) VALUES %s
            RETURNING receipt_id
        """
        
        values = [
            (
                r['receipt_date'],
                r['vendor_name'],
                r['gross_amount'],
                r['gst_amount'],
                r['net_amount'],
                r['description'],
                r['category'],
                False,  # created_from_banking=False (GoDaddy manual import)
                r['source_hash']
            )
            for r in receipts_to_import
        ]
        
        execute_values(cur, insert_query, values)
        inserted = cur.rowcount
        
        conn.commit()
        
        print(f"✅ IMPORT COMPLETE: {inserted} receipts imported successfully")
        
        # Verification
        cur.execute("""
            SELECT COUNT(*), SUM(gross_amount) as total
            FROM receipts
            WHERE vendor_name = 'GoDaddy'
        """)
        count, total = cur.fetchone()
        print(f"\n✅ VERIFICATION:")
        print(f"   Total GoDaddy receipts: {count}")
        print(f"   Total amount: ${total:,.2f}")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        conn.rollback()
        conn.close()
        return False

if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Import GoDaddy receipts from CSV')
    parser.add_argument('--write', action='store_true', help='Apply changes to database')
    parser.add_argument('--dry-run', action='store_true', default=True, help='Preview without applying')
    parser.add_argument('--file', default='l:\\limo\\godaddy\\godaddyreceipts.csv', help='CSV file path')
    
    args = parser.parse_args()
    
    success = import_godaddy_receipts(
        args.file,
        write=args.write,
        dry_run=not args.write
    )
    
    sys.exit(0 if success else 1)
