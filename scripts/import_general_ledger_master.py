"""
Master data importer for almsdata - handles all missing data systematically.
Phase 1: General Ledger import (highest priority - fills GL gap for all years)
"""
import os
import sys
import pandas as pd
import psycopg2
from datetime import datetime
import hashlib


def env(name, default=None):
    return os.environ.get(name, default)


def get_db_connection():
    return psycopg2.connect(
        host=env("DB_HOST", "localhost"),
        dbname=env("DB_NAME", "almsdata"),
        user=env("DB_USER", "postgres"),
        password=env("DB_PASSWORD", "***REMOVED***"),
    )


def import_general_ledger(file_path, dry_run=False):
    """Import General Ledger from QuickBooks Excel export."""
    print(f"\n{'[DRY RUN] ' if dry_run else ''}Importing General Ledger from: {file_path}")
    
    # Read Excel with QuickBooks format (skip header rows)
    df = pd.read_excel(file_path, header=4)
    
    print(f"Loaded {len(df)} rows")
    print(f"Columns: {list(df.columns)}")
    
    # Normalize column names
    df.columns = df.columns.str.strip()
    
    # Expected columns: Date, Transaction Type, #, Name, Memo/Description, Account, Debit, Credit, Balance
    # Map to our schema
    col_map = {
        'Date': 'transaction_date',
        'Account': 'account_code',
        'Memo/Description': 'description',
        'Debit': 'debit_amount',
        'Credit': 'credit_amount',
        'Transaction Type': 'transaction_type',
        '#': 'transaction_number',
        'Name': 'entity_name',
    }
    
    # Rename columns
    for old, new in col_map.items():
        if old in df.columns:
            df[new] = df[old]
    
    # Filter out rows without dates (account headers, totals)
    df = df[df['transaction_date'].notna()]
    
    # Convert dates
    df['transaction_date'] = pd.to_datetime(df['transaction_date'], errors='coerce')
    df = df[df['transaction_date'].notna()]
    
    # Convert amounts
    df['debit_amount'] = pd.to_numeric(df['debit_amount'], errors='coerce').fillna(0)
    df['credit_amount'] = pd.to_numeric(df['credit_amount'], errors='coerce').fillna(0)
    
    # Fill missing values and convert types
    df['account_code'] = df['account_code'].fillna('').astype(str)
    df['description'] = df['description'].fillna('').astype(str)
    df['transaction_type'] = df.get('transaction_type', pd.Series([''] * len(df))).fillna('').astype(str)
    df['transaction_number'] = df.get('transaction_number', pd.Series([''] * len(df))).fillna('').astype(str)
    df['entity_name'] = df.get('entity_name', pd.Series([''] * len(df))).fillna('').astype(str)
    
    # Add source system
    df['source_system'] = 'QuickBooks'
    df['source_transaction_id'] = df['transaction_number']
    
    # Create unique hash for deduplication
    def create_hash(row):
        components = [
            str(row['transaction_date']),
            str(row['account_code']),
            str(row['description']),
            str(row['debit_amount']),
            str(row['credit_amount']),
        ]
        return hashlib.sha256('|'.join(components).encode()).hexdigest()
    
    df['row_hash'] = df.apply(create_hash, axis=1)
    
    print(f"\nProcessed {len(df)} valid GL entries")
    print(f"Date range: {df['transaction_date'].min()} to {df['transaction_date'].max()}")
    print(f"Debits total: ${df['debit_amount'].sum():,.2f}")
    print(f"Credits total: ${df['credit_amount'].sum():,.2f}")
    
    # Year breakdown
    df['year'] = df['transaction_date'].dt.year
    year_counts = df.groupby('year').size().sort_index()
    print("\nEntries by year:")
    for year, count in year_counts.items():
        print(f"  {year}: {count:,} entries")
    
    if dry_run:
        print("\n[OK] DRY RUN complete - no data written to database")
        return {'dry_run': True, 'rows': len(df)}
    
    # Write to database
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        
        # Check if unified_general_ledger exists
        cur.execute("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_schema='public' AND table_name='unified_general_ledger'
            )
        """)
        table_exists = cur.fetchone()[0]
        
        if not table_exists:
            print("\n📋 Creating unified_general_ledger table...")
            cur.execute("""
                CREATE TABLE unified_general_ledger (
                    id SERIAL PRIMARY KEY,
                    transaction_date DATE NOT NULL,
                    account_code VARCHAR(100),
                    account_name VARCHAR(200),
                    description TEXT,
                    debit_amount DECIMAL(15,2) DEFAULT 0,
                    credit_amount DECIMAL(15,2) DEFAULT 0,
                    source_system VARCHAR(50),
                    source_transaction_id VARCHAR(100),
                    transaction_type VARCHAR(50),
                    transaction_number VARCHAR(50),
                    entity_name VARCHAR(200),
                    row_hash VARCHAR(64) UNIQUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cur.execute("CREATE INDEX idx_ugl_date ON unified_general_ledger(transaction_date)")
            cur.execute("CREATE INDEX idx_ugl_account ON unified_general_ledger(account_code)")
            conn.commit()
            print("[OK] Table created")
        
        # Prepare rows for insert
        rows = []
        for _, row in df.iterrows():
            rows.append((
                row['transaction_date'],
                row['account_code'][:100] if row['account_code'] else None,
                None,  # account_name (will populate later from chart of accounts)
                row['description'],
                float(row['debit_amount']),
                float(row['credit_amount']),
                row['source_system'],
                row['source_transaction_id'][:100] if row['source_transaction_id'] else None,
                row['transaction_type'][:50] if row['transaction_type'] else None,
                row['transaction_number'][:50] if row['transaction_number'] else None,
                row['entity_name'][:200] if row['entity_name'] else None,
                row['row_hash'],
            ))
        
        # Insert with ON CONFLICT (idempotent)
        print(f"\n💾 Inserting {len(rows)} rows to unified_general_ledger...")
        inserted = 0
        duplicates = 0
        
        for row in rows:
            try:
                cur.execute("""
                    INSERT INTO unified_general_ledger (
                        transaction_date, account_code, account_name, description,
                        debit_amount, credit_amount, source_system, source_transaction_id,
                        transaction_type, transaction_number, entity_name, row_hash
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (row_hash) DO NOTHING
                """, row)
                if cur.rowcount > 0:
                    inserted += 1
                else:
                    duplicates += 1
            except Exception as e:
                print(f"[WARN]  Error inserting row: {e}")
                continue
        
        conn.commit()
        
        print(f"\n[OK] General Ledger import complete:")
        print(f"  - Inserted: {inserted:,} new entries")
        print(f"  - Duplicates skipped: {duplicates:,}")
        
        return {
            'dry_run': False,
            'total_rows': len(df),
            'inserted': inserted,
            'duplicates': duplicates,
        }
        
    finally:
        try:
            conn.close()
        except:
            pass


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Import General Ledger to unified_general_ledger")
    parser.add_argument('--file', default='L:\\limo\\quickbooks\\Arrow Limousine backup 2025 Oct 19, 2025\\General_ledger.xlsx',
                        help='Path to General Ledger Excel file')
    parser.add_argument('--dry-run', action='store_true', help='Preview import without writing to database')
    args = parser.parse_args()
    
    if not os.path.exists(args.file):
        print(f"[FAIL] File not found: {args.file}")
        sys.exit(1)
    
    result = import_general_ledger(args.file, dry_run=args.dry_run)
    
    if not result['dry_run']:
        print(f"\n🎉 SUCCESS: {result['inserted']:,} GL entries imported to almsdata")


if __name__ == "__main__":
    main()
