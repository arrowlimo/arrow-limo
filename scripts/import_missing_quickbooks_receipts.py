#!/usr/bin/env python3
"""
Import Missing QuickBooks Receipts to Database
Import the 847 missing QuickBooks expense transactions worth $606K+ into receipts table
"""

import pandas as pd
import psycopg2
import os
import hashlib
from datetime import datetime
from decimal import Decimal

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***')
    )

def import_quickbooks_receipts(dry_run=True):
    """Import missing QuickBooks receipts to database"""
    print("📥 QUICKBOOKS RECEIPTS IMPORT")
    print("=" * 50)
    print("Mode:", "DRY RUN (preview only)" if dry_run else "APPLY CHANGES")
    print("=" * 50)
    
    # Load QuickBooks data
    qb_file = 'l:\\limo\\staging\\2012_parsed\\2012_quickbooks_transactions.csv'
    qb_data = pd.read_csv(qb_file)
    
    # Filter to expense transactions only
    expenses = qb_data[qb_data['withdrawal'].notna() & (qb_data['withdrawal'] > 0)].copy()
    
    print(f"📄 Loaded {len(expenses)} QuickBooks expense transactions")
    print(f"💰 Total amount: ${expenses['withdrawal'].sum():,.2f}")
    
    # Prepare data for import
    expenses['receipt_date'] = pd.to_datetime(expenses['date'], format='%m/%d/%Y', errors='coerce')
    
    # Filter to 2012 only (some data extends beyond)
    expenses_2012 = expenses[expenses['receipt_date'].dt.year == 2012].copy()
    
    print(f"📅 2012 transactions: {len(expenses_2012)}")
    print(f"💰 2012 amount: ${expenses_2012['withdrawal'].sum():,.2f}")
    
    # Clean and prepare fields - handle null descriptions
    expenses_2012['vendor_name'] = expenses_2012['description'].fillna('Unknown Vendor').str.strip().str[:200]
    expenses_2012['gross_amount'] = expenses_2012['withdrawal']
    expenses_2012['description'] = expenses_2012['description'].fillna('QuickBooks Transaction')
    
    # Calculate GST (5% included in Alberta)
    expenses_2012['gst_amount'] = expenses_2012['gross_amount'] * 0.05 / 1.05
    expenses_2012['net_amount'] = expenses_2012['gross_amount'] - expenses_2012['gst_amount']
    
    expenses_2012['source_system'] = 'QuickBooks-2012-Import'
    expenses_2012['source_reference'] = 'QB-2012-' + expenses_2012.index.astype(str)
    expenses_2012['currency'] = 'CAD'
    expenses_2012['validation_status'] = 'imported'
    expenses_2012['created_at'] = datetime.now()
    
    # Generate unique source_hash values to handle duplicates
    import hashlib
    expenses_2012['base_hash'] = expenses_2012.apply(lambda row: 
        f"{row['receipt_date']}|{row['vendor_name']}|{row['gross_amount']}|{row['description']}", axis=1)
    
    # Handle duplicate base hashes by adding sequence numbers
    hash_counts = {}
    source_hashes = []
    
    for base_hash in expenses_2012['base_hash']:
        if base_hash not in hash_counts:
            hash_counts[base_hash] = 0
            source_hash = hashlib.md5(base_hash.encode()).hexdigest()
        else:
            hash_counts[base_hash] += 1
            unique_hash = f"{base_hash}|SEQ-{hash_counts[base_hash]}"
            source_hash = hashlib.md5(unique_hash.encode()).hexdigest()
        source_hashes.append(source_hash)
    
    expenses_2012['source_hash'] = source_hashes
    expenses_2012.drop('base_hash', axis=1, inplace=True)
    
    # Categorize expenses
    def categorize_expense(description):
        desc_lower = str(description).lower()
        
        if any(fuel in desc_lower for fuel in ['shell', 'petro', 'esso', 'fas gas', 'chevron']):
            return 'fuel'
        elif any(bank in desc_lower for bank in ['bank charge', 'bank fee', 'interest']):
            return 'bank_fees'
        elif any(vehicle in desc_lower for vehicle in ['heffner', 'toyota', 'lexus', 'hertz']):
            return 'vehicle'
        elif any(comm in desc_lower for comm in ['phone', 'telus', 'rogers', 'sasktel']):
            return 'communication'
        elif any(ins in desc_lower for ins in ['optimum', 'insurance', 'co-operators']):
            return 'insurance'
        elif 'paul richard' in desc_lower:
            return 'owner_draws'
        elif any(food in desc_lower for food in ['save on foods', 'liquor']):
            return 'meals_entertainment'
        else:
            return 'expense'
    
    expenses_2012['category'] = expenses_2012['description'].apply(categorize_expense)
    
    # Show preview
    print(f"\n📊 IMPORT PREVIEW (Top 10 by amount):")
    preview = expenses_2012.nlargest(10, 'gross_amount')
    for _, row in preview.iterrows():
        print(f"   {row['receipt_date'].strftime('%Y-%m-%d')}: {row['vendor_name'][:40]} - ${row['gross_amount']:,.2f} ({row['category']})")
    
    # Category breakdown
    print(f"\n📊 CATEGORY BREAKDOWN:")
    category_summary = expenses_2012.groupby('category')['gross_amount'].agg(['count', 'sum']).sort_values('sum', ascending=False)
    for category, (count, total) in category_summary.iterrows():
        print(f"   {category}: {count} transactions, ${total:,.2f}")
    
    if dry_run:
        print(f"\n👀 DRY RUN COMPLETE")
        print(f"   Ready to import: {len(expenses_2012)} transactions")
        print(f"   Total value: ${expenses_2012['gross_amount'].sum():,.2f}")
        print(f"   Total GST: ${expenses_2012['gst_amount'].sum():,.2f}")
        print(f"\n📋 To apply import, run: python {__file__} --apply")
        return expenses_2012
    
    # Actual import
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Check for existing QuickBooks imports
        cur.execute("SELECT COUNT(*) FROM receipts WHERE source_system = 'QuickBooks-2012-Import'")
        existing_count = cur.fetchone()[0]
        
        if existing_count > 0:
            print(f"[WARN]  WARNING: {existing_count} QuickBooks receipts already exist!")
            response = input("Continue anyway? (y/N): ")
            if response.lower() != 'y':
                print("[FAIL] Import cancelled")
                return None
        
        print(f"\n📥 IMPORTING {len(expenses_2012)} RECEIPTS...")
        
        imported_count = 0
        error_count = 0
        
        for _, row in expenses_2012.iterrows():
            try:
                # Use individual transactions to avoid abort cascade
                cur.execute("""
                    INSERT INTO receipts (
                        source_system, source_reference, receipt_date, vendor_name,
                        description, currency, gross_amount, gst_amount,
                        category, validation_status, created_at, source_hash
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    row['source_system'],
                    row['source_reference'],
                    row['receipt_date'],
                    row['vendor_name'],
                    row['description'],
                    row['currency'],
                    float(row['gross_amount']) if pd.notna(row['gross_amount']) else 0.0,
                    float(row['gst_amount']) if pd.notna(row['gst_amount']) else 0.0,
                    row['category'],
                    row['validation_status'],
                    row['created_at'],
                    row['source_hash']
                ))
                
                # Commit each row individually
                conn.commit()
                imported_count += 1
                
                if imported_count % 100 == 0:
                    print(f"   Imported {imported_count} receipts...")
                    
            except Exception as e:
                error_count += 1
                print(f"   [FAIL] Error importing row {row['source_reference']}: {str(e)}")
                # Rollback this failed transaction and continue
                conn.rollback()
                continue
        
        print(f"\n📊 IMPORT SUMMARY:")
        print(f"   [OK] Successfully imported: {imported_count} receipts")
        print(f"   [FAIL] Failed imports: {error_count} receipts")
        
        print(f"\n[OK] IMPORT COMPLETE")
        print(f"   Successfully imported: {imported_count} receipts")
        print(f"   Total value: ${expenses_2012['gross_amount'].sum():,.2f}")
        print(f"   Total GST: ${expenses_2012['gst_amount'].sum():,.2f}")
        
        # Verify import
        cur.execute("SELECT COUNT(*), SUM(gross_amount) FROM receipts WHERE source_system = 'QuickBooks-2012-Import'")
        verify_count, verify_amount = cur.fetchone()
        
        print(f"\n🔍 VERIFICATION:")
        print(f"   Receipts in database: {verify_count}")
        print(f"   Total amount: ${float(verify_amount):,.2f}")
        
        return expenses_2012
        
    except Exception as e:
        print(f"[FAIL] IMPORT ERROR: {str(e)}")
        conn.rollback()
        return None
        
    finally:
        cur.close()
        conn.close()

def main():
    """Main import function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Import Missing QuickBooks Receipts')
    parser.add_argument('--apply', action='store_true', help='Apply the import (default is dry-run)')
    
    args = parser.parse_args()
    
    result = import_quickbooks_receipts(dry_run=not args.apply)
    
    if result is not None and not args.apply:
        print(f"\n🎯 AUDIT IMPACT PREVIEW:")
        print(f"   This will fix the 2012 expense audit issue")
        print(f"   Additional expenses: ${result['gross_amount'].sum():,.2f}")
        print(f"   Additional GST deductions: ${result['gst_amount'].sum():,.2f}")
        print(f"   Improved expense categorization for CRA compliance")

if __name__ == "__main__":
    main()