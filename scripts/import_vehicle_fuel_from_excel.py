#!/usr/bin/env python3
"""
Import vehicle fuel data from Excel receipts file to vehicle_fuel_log table.

This script:
1. Reads the Excel receipts file (L:\limo\reports\new receipts fileoct.xlsx)
2. Filters for records that have both vehicle_id AND fuel amount data
3. Maps Excel columns to vehicle_fuel_log schema:
   - vehicle_id -> vehicle_id (convert to text)
   - fuel -> amount (fuel purchase amount in dollars)
   - receipt_date -> recorded_at 
   - id -> receipt_id (Excel row ID for tracking)
4. Includes duplicate detection and safety checks
5. Provides dry-run mode for validation

Usage:
  python scripts/import_vehicle_fuel_from_excel.py --dry-run    # Preview only
  python scripts/import_vehicle_fuel_from_excel.py --commit    # Actually import
"""
import os
import sys
import argparse
import pandas as pd
import psycopg2
import hashlib
from datetime import datetime

# Database connection
DB_CONFIG = {
    'dbname': os.environ.get('DB_NAME', 'almsdata'),
    'user': os.environ.get('DB_USER', 'postgres'),
    'password': os.environ.get('DB_PASSWORD', '***REMOVED***'),
    'host': os.environ.get('DB_HOST', 'localhost'),
    'port': int(os.environ.get('DB_PORT', '5432'))
}

XLSX_PATH = r"L:\limo\reports\new receipts fileoct.xlsx"

def load_fuel_data():
    """Load and filter fuel data from Excel"""
    if not os.path.exists(XLSX_PATH):
        raise FileNotFoundError(f"Excel file not found: {XLSX_PATH}")
    
    print(f"📊 Loading Excel file: {XLSX_PATH}")
    xl = pd.ExcelFile(XLSX_PATH)
    df = xl.parse('receipts')
    
    print(f"📋 Total records in Excel: {len(df)}")
    
    # Filter for records with both vehicle_id AND fuel amount
    fuel_filter = (
        df['vehicle_id'].notna() & 
        df['fuel'].notna() &
        (df['fuel'] > 0)  # Exclude zero/negative fuel amounts
    )
    
    fuel_df = df[fuel_filter].copy()
    print(f"🚗 Records with vehicle_id AND fuel data: {len(fuel_df)}")
    
    if len(fuel_df) == 0:
        print("[FAIL] No fuel records found with both vehicle_id and fuel amount")
        return None
    
    # Clean and prepare data
    fuel_df['vehicle_id_clean'] = pd.to_numeric(fuel_df['vehicle_id'], errors='coerce')
    fuel_df['vehicle_id_str'] = fuel_df['vehicle_id_clean'].fillna(0).astype(int).astype(str)
    fuel_df['fuel_amount'] = pd.to_numeric(fuel_df['fuel'], errors='coerce')
    fuel_df['receipt_date_clean'] = pd.to_datetime(fuel_df['receipt_date'], errors='coerce')
    
    # Handle missing receipt IDs - use row index + offset for fuel records
    fuel_df['receipt_id_original'] = pd.to_numeric(fuel_df['id'], errors='coerce')
    # Create synthetic receipt IDs for fuel records (use negative numbers to avoid conflicts)
    fuel_df.reset_index(inplace=True)
    fuel_df['receipt_id'] = fuel_df['receipt_id_original'].fillna(-(fuel_df.index + 100000))
    fuel_df['receipt_id'] = fuel_df['receipt_id'].astype(int)
    
    # Remove records with invalid data after cleaning
    valid_filter = (
        fuel_df['fuel_amount'].notna() & 
        fuel_df['receipt_date_clean'].notna() & 
        fuel_df['vehicle_id_clean'].notna() &
        (fuel_df['fuel_amount'] > 0) &
        (fuel_df['vehicle_id_clean'] > 0)
    )
    
    clean_df = fuel_df[valid_filter].copy()
    print(f"[OK] Clean fuel records after validation: {len(clean_df)}")
    
    if len(clean_df) != len(fuel_df):
        print(f"[WARN]  Filtered out {len(fuel_df) - len(clean_df)} invalid records")
    
    return clean_df

def generate_fuel_hash(vehicle_id, amount, date, receipt_id):
    """Generate unique hash for duplicate detection"""
    hash_string = f"{vehicle_id}|{amount}|{date.date()}|{receipt_id}"
    return hashlib.sha256(hash_string.encode()).hexdigest()[:16]

def check_existing_records(cur, fuel_df):
    """Check for existing records in vehicle_fuel_log"""
    print("🔍 Checking for existing records...")
    
    # Since we're using synthetic receipt IDs, check for duplicates by vehicle_id, amount, and date
    existing_count = 0
    duplicate_hashes = set()
    
    if len(fuel_df) > 0:
        # Check existing records using a hash of key fields
        for _, row in fuel_df.iterrows():
            fuel_hash = generate_fuel_hash(
                row['vehicle_id_str'], 
                row['fuel_amount'], 
                row['receipt_date_clean'], 
                row['receipt_id']
            )
            
            cur.execute("""
                SELECT COUNT(*) FROM vehicle_fuel_log 
                WHERE vehicle_id = %s 
                AND amount = %s 
                AND DATE(recorded_at) = %s
            """, (
                row['vehicle_id_str'],
                float(row['fuel_amount']),
                row['receipt_date_clean'].date()
            ))
            
            if cur.fetchone()[0] > 0:
                duplicate_hashes.add(fuel_hash)
                existing_count += 1
    
    if existing_count > 0:
        print(f"[WARN]  Found {existing_count} potential duplicate records by vehicle/amount/date")
    else:
        print("[OK] No duplicate records found - all records appear new")
    
    return duplicate_hashes

def preview_import_data(fuel_df, duplicate_hashes):
    """Show preview of data to be imported"""
    # Filter out records that match duplicate hashes  
    fuel_df['record_hash'] = fuel_df.apply(
        lambda row: generate_fuel_hash(
            row['vehicle_id_str'], 
            row['fuel_amount'], 
            row['receipt_date_clean'], 
            row['receipt_id']
        ), axis=1
    )
    
    new_records = fuel_df[~fuel_df['record_hash'].isin(duplicate_hashes)]
    
    print(f"\n📋 Import Preview:")
    print(f"   Total fuel records: {len(fuel_df)}")
    print(f"   Potential duplicates: {len(duplicate_hashes)}")
    print(f"   New to import: {len(new_records)}")
    
    if len(new_records) > 0:
        print(f"\n📊 New Records Summary:")
        print(f"   Vehicle IDs: {sorted(new_records['vehicle_id_str'].unique())}")
        print(f"   Date range: {new_records['receipt_date_clean'].min().date()} to {new_records['receipt_date_clean'].max().date()}")
        print(f"   Fuel amounts: ${new_records['fuel_amount'].min():.2f} to ${new_records['fuel_amount'].max():.2f}")
        print(f"   Average fuel amount: ${new_records['fuel_amount'].mean():.2f}")
        
        print(f"\n📝 Sample Records:")
        for idx, (_, row) in enumerate(new_records.head(5).iterrows()):
            print(f"   {idx+1}. Vehicle {row['vehicle_id_str']}: ${row['fuel_amount']:.2f} on {row['receipt_date_clean'].date()}")
            print(f"      Synthetic ID: {row['receipt_id']}, Vendor: {row.get('vendor_name', 'N/A')}")
    
    return new_records

def import_fuel_records(cur, new_records, dry_run=True):
    """Import fuel records to database"""
    if len(new_records) == 0:
        print("[OK] No new records to import")
        return 0
    
    print(f"\n{'🔍 DRY RUN:' if dry_run else '💾 IMPORTING:'} Processing {len(new_records)} fuel records...")
    
    imported = 0
    errors = 0
    
    for _, row in new_records.iterrows():
        try:
            if not dry_run:
                cur.execute("""
                    INSERT INTO vehicle_fuel_log (
                        vehicle_id, amount, receipt_id, recorded_at, recorded_by
                    ) VALUES (%s, %s, %s, %s, %s)
                """, (
                    row['vehicle_id_str'],
                    float(row['fuel_amount']),
                    int(row['receipt_id']),
                    row['receipt_date_clean'],
                    'excel_import'
                ))
            
            imported += 1
            if imported % 50 == 0:
                print(f"   📈 {'Previewed' if dry_run else 'Imported'} {imported} records...")
                
        except Exception as e:
            print(f"[WARN]  Error on record {row['receipt_id']}: {e}")
            errors += 1
            if not dry_run:
                cur.connection.rollback()
    
    print(f"[OK] {'Preview complete' if dry_run else 'Import complete'}: {imported} records {'previewed' if dry_run else 'imported'}")
    if errors > 0:
        print(f"[WARN]  {errors} errors encountered")
    
    return imported

def main():
    parser = argparse.ArgumentParser(description='Import vehicle fuel data from Excel')
    parser.add_argument('--dry-run', action='store_true', help='Preview import without making changes')
    parser.add_argument('--commit', action='store_true', help='Actually perform the import')
    
    args = parser.parse_args()
    
    if not args.dry_run and not args.commit:
        print("[FAIL] Must specify either --dry-run or --commit")
        sys.exit(1)
    
    try:
        # Load fuel data from Excel
        fuel_df = load_fuel_data()
        if fuel_df is None or len(fuel_df) == 0:
            print("[FAIL] No fuel data to process")
            return
        
        # Connect to database
        print(f"\n🔌 Connecting to database...")
        with psycopg2.connect(**DB_CONFIG) as conn:
            cur = conn.cursor()
            
            # Check existing records
            existing_receipt_ids = check_existing_records(cur, fuel_df)
            
            # Preview import
            new_records = preview_import_data(fuel_df, existing_receipt_ids)
            
            # Import (or preview)
            imported_count = import_fuel_records(cur, new_records, dry_run=args.dry_run)
            
            if not args.dry_run and imported_count > 0:
                conn.commit()
                print(f"[OK] Successfully committed {imported_count} fuel records to database")
            elif args.dry_run:
                print(f"\n💡 To actually import these {len(new_records)} records, run:")
                print(f"   python scripts/import_vehicle_fuel_from_excel.py --commit")
                
    except Exception as e:
        print(f"[FAIL] Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()