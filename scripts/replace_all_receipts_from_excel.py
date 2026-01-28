"""
Replace ALL receipts in database with cleaned Excel export.

CAUTION: This will DELETE all existing receipts and import fresh from Excel.
"""

import pandas as pd
import psycopg2
import os
from datetime import datetime

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***')
    )

def main():
    print("="*80)
    print("REPLACE ALL RECEIPTS FROM EXCEL")
    print("="*80)
    
    excel_file = 'L:\\limo\\reports\\receipts_complete_export.xlsx'
    
    # Load Excel
    print(f"\nLoading Excel file: {excel_file}")
    df = pd.read_excel(excel_file)
    
    print(f"Excel contains {len(df):,} receipts")
    print(f"Columns: {len(df.columns)}")
    
    # Show summary
    print("\n" + "="*80)
    print("EXCEL DATA SUMMARY")
    print("="*80)
    print(f"Date range: {df['receipt_date'].min()} to {df['receipt_date'].max()}")
    print(f"Total gross_amount: ${df['gross_amount'].sum():,.2f}")
    print(f"Vendors: {df['vendor_name'].nunique():,} unique")
    
    # Connect to database
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Check current database state
    print("\n" + "="*80)
    print("CURRENT DATABASE STATE")
    print("="*80)
    
    cur.execute("SELECT COUNT(*) FROM receipts")
    db_count = cur.fetchone()[0]
    print(f"Database contains {db_count:,} receipts")
    
    cur.execute("SELECT MIN(receipt_date), MAX(receipt_date) FROM receipts")
    db_dates = cur.fetchone()
    print(f"Date range: {db_dates[0]} to {db_dates[1]}")
    
    cur.execute("SELECT SUM(gross_amount) FROM receipts")
    db_total = cur.fetchone()[0]
    print(f"Total gross_amount: ${db_total:,.2f}")
    
    # Check for foreign key dependencies
    print("\n" + "="*80)
    print("CHECKING FOREIGN KEY DEPENDENCIES")
    print("="*80)
    
    cur.execute("SELECT COUNT(*) FROM banking_receipt_matching_ledger")
    banking_links = cur.fetchone()[0]
    print(f"banking_receipt_matching_ledger: {banking_links:,} links")
    
    cur.execute("SELECT COUNT(*) FROM banking_transactions WHERE receipt_id IS NOT NULL")
    banking_txn_links = cur.fetchone()[0]
    print(f"banking_transactions.receipt_id: {banking_txn_links:,} links")
    
    # Warning
    print("\n" + "="*80)
    print("⚠️  WARNING ⚠️")
    print("="*80)
    print(f"\nThis will:")
    print(f"  1. DELETE all {db_count:,} receipts from database")
    print(f"  2. DELETE {banking_links:,} banking_receipt_matching_ledger links")
    print(f"  3. NULL {banking_txn_links:,} banking_transactions.receipt_id references")
    print(f"  4. IMPORT {len(df):,} receipts from Excel")
    print(f"\nThis operation CANNOT be easily undone!")
    
    response = input("\nType 'REPLACE ALL' to proceed: ")
    if response != 'REPLACE ALL':
        print("Aborted")
        return
    
    # Create full backup
    print("\n" + "="*80)
    print("CREATING FULL BACKUP")
    print("="*80)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_table = f'receipts_full_backup_{timestamp}'
    
    cur.execute(f"CREATE TABLE {backup_table} AS SELECT * FROM receipts")
    cur.execute(f"SELECT COUNT(*) FROM {backup_table}")
    backup_count = cur.fetchone()[0]
    print(f"✅ Created backup: {backup_table} ({backup_count:,} rows)")
    
    # Backup banking links
    banking_backup = f'banking_receipt_matching_ledger_backup_{timestamp}'
    cur.execute(f"CREATE TABLE {banking_backup} AS SELECT * FROM banking_receipt_matching_ledger")
    cur.execute(f"SELECT COUNT(*) FROM {banking_backup}")
    banking_backup_count = cur.fetchone()[0]
    print(f"✅ Created backup: {banking_backup} ({banking_backup_count:,} rows)")
    
    # Delete banking links first
    print("\n" + "="*80)
    print("DELETING BANKING LINKS")
    print("="*80)
    
    cur.execute("DELETE FROM banking_receipt_matching_ledger")
    deleted_links = cur.rowcount
    print(f"✅ Deleted {deleted_links:,} banking_receipt_matching_ledger links")
    
    # NULL out banking_transactions.receipt_id references
    print("\n" + "="*80)
    print("NULLING BANKING_TRANSACTIONS REFERENCES")
    print("="*80)
    
    cur.execute("UPDATE banking_transactions SET receipt_id = NULL WHERE receipt_id IS NOT NULL")
    nulled_refs = cur.rowcount
    print(f"✅ Nulled {nulled_refs:,} banking_transactions.receipt_id references")
    
    # Delete all receipts
    print("\n" + "="*80)
    print("DELETING ALL RECEIPTS")
    print("="*80)
    
    cur.execute("DELETE FROM receipts")
    deleted_receipts = cur.rowcount
    print(f"✅ Deleted {deleted_receipts:,} receipts")
    
    # Import from Excel
    print("\n" + "="*80)
    print("IMPORTING FROM EXCEL")
    print("="*80)
    
    # Get column names from database
    cur.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'receipts' 
        ORDER BY ordinal_position
    """)
    db_columns = [row[0] for row in cur.fetchall()]
    
    # Match Excel columns to database columns
    excel_cols = df.columns.tolist()
    matched_cols = [col for col in excel_cols if col in db_columns]
    
    print(f"Matched {len(matched_cols)} columns out of {len(excel_cols)} Excel columns")
    
    # Prepare INSERT statement
    cols_str = ', '.join(matched_cols)
    placeholders = ', '.join(['%s'] * len(matched_cols))
    
    insert_sql = f"INSERT INTO receipts ({cols_str}) VALUES ({placeholders})"
    
    # Insert in batches
    batch_size = 1000
    total_inserted = 0
    
    for i in range(0, len(df), batch_size):
        batch = df.iloc[i:i+batch_size]
        
        # Prepare values
        values = []
        for _, row in batch.iterrows():
            row_values = []
            for col in matched_cols:
                val = row[col]
                # Handle NaN/None
                if pd.isna(val):
                    row_values.append(None)
                else:
                    row_values.append(val)
            values.append(tuple(row_values))
        
        # Execute batch insert
        cur.executemany(insert_sql, values)
        total_inserted += len(values)
        
        if (i + batch_size) % 5000 == 0:
            print(f"  Inserted {total_inserted:,} / {len(df):,} receipts...")
    
    print(f"✅ Inserted {total_inserted:,} receipts")
    
    # Commit
    conn.commit()
    
    # Verify
    print("\n" + "="*80)
    print("VERIFICATION")
    print("="*80)
    
    cur.execute("SELECT COUNT(*) FROM receipts")
    new_count = cur.fetchone()[0]
    print(f"Database now contains {new_count:,} receipts")
    
    cur.execute("SELECT MIN(receipt_date), MAX(receipt_date) FROM receipts")
    new_dates = cur.fetchone()
    print(f"Date range: {new_dates[0]} to {new_dates[1]}")
    
    cur.execute("SELECT SUM(gross_amount) FROM receipts")
    new_total = cur.fetchone()[0]
    print(f"Total gross_amount: ${new_total:,.2f}")
    
    if new_count == len(df):
        print("\n✅ SUCCESS! All receipts imported correctly")
    else:
        print(f"\n⚠️  WARNING: Expected {len(df):,} but got {new_count:,}")
    
    print("\n" + "="*80)
    print("REPLACEMENT COMPLETE")
    print("="*80)
    print(f"\n✅ Replaced {deleted_receipts:,} old receipts with {new_count:,} cleaned receipts")
    print(f"✅ Backups created:")
    print(f"   - {backup_table}")
    print(f"   - {banking_backup}")
    print(f"\n⚠️  NOTE: Banking links were deleted and need to be recreated")
    print(f"   Run: python scripts/match_all_receipts_to_banking.py --write")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
