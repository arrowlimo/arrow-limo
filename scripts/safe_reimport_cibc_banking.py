#!/usr/bin/env python3
"""
Safe re-import of compiled CIBC CSV files with proper error handling.
Handles transaction errors gracefully and provides detailed logging.

Usage:
  python scripts/safe_reimport_cibc_banking.py
"""
import os
import pandas as pd
import psycopg2
import hashlib
from datetime import datetime

# Database connection
DB_CONFIG = {
    'dbname': os.environ.get('DB_NAME', 'almsdata'),
    'user': os.environ.get('DB_USER', 'postgres'),
    'password': os.environ.get('DB_PASSWORD', '***REDACTED***'),
    'host': os.environ.get('DB_HOST', 'localhost'),
    'port': int(os.environ.get('DB_PORT', '5432'))
}

# Account mappings
ACCOUNTS = {
    '8362': {
        'file': r'L:\limo\CIBC UPLOADS\0228362 (CIBC checking account)\cibc 8362 all.csv',
        'account_number': '0228362',
        'account_name': 'CIBC checking account'
    },
    '8117': {
        'file': r'L:\limo\CIBC UPLOADS\3648117 (CIBC Business Deposit account, alias for 0534\cibc 8117 all.csv',
        'account_number': '3648117',
        'account_name': 'CIBC Business Deposit account'
    },
    '4462': {
        'file': r'L:\limo\CIBC UPLOADS\8314462 (CIBC vehicle loans)\cibc 4462 all.csv',
        'account_number': '8314462',
        'account_name': 'CIBC vehicle loans'
    }
}

def generate_transaction_hash(trans_date, description, amount, account_number):
    """Generate unique hash for transaction deduplication"""
    hash_string = f"{trans_date}|{description}|{amount}|{account_number}"
    return hashlib.sha256(hash_string.encode()).hexdigest()[:16]

def clear_account_data(cur, account_number):
    """Clear existing data for specific account"""
    cur.execute(
        "DELETE FROM banking_transactions WHERE account_number = %s",
        (account_number,)
    )
    rows_deleted = cur.rowcount
    print(f"Cleared {rows_deleted} existing records for account {account_number}")

def import_csv_file(cur, file_path, account_number, account_name):
    """Import CSV data for one account with proper error handling"""
    if not os.path.exists(file_path):
        print(f"[FAIL] File not found: {file_path}")
        return 0
    
    try:
        # Read CSV with proper headers
        df = pd.read_csv(file_path)
        print(f"📁 File: {os.path.basename(file_path)}")
        print(f"📊 Columns: {df.columns.tolist()}")
        print(f"📏 Shape: {df.shape}")
        
        # Handle different column formats
        if 'Trans_date' in df.columns:
            # Compiled format: Bank_id,Trans_date,Trans_description,Debit,Credit,Reconsiled_receipt_id,Reconsiled_receipt_total
            df = df.rename(columns={
                'Trans_date': 'transaction_date',
                'Trans_description': 'description', 
                'Debit': 'debit_amount',
                'Credit': 'credit_amount'
            })
        else:
            print(f"[FAIL] Unexpected column format in {file_path}")
            return 0
            
    except Exception as e:
        print(f"[FAIL] Error reading {file_path}: {e}")
        return 0
    
    # Clean and process data
    original_count = len(df)
    df = df.dropna(subset=['transaction_date', 'description'])
    df['transaction_date'] = pd.to_datetime(df['transaction_date'], errors='coerce')
    df = df.dropna(subset=['transaction_date'])
    
    print(f"📋 Records after cleaning: {len(df)} (from {original_count})")
    
    # Convert amounts
    for col in ['debit_amount', 'credit_amount']:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    
    # Insert records with individual commits
    inserted = 0
    errors = 0
    
    for idx, row in df.iterrows():
        try:
            # Generate transaction hash
            amount = max(row['debit_amount'], row['credit_amount'])
            tx_hash = generate_transaction_hash(
                row['transaction_date'].date(),
                row['description'],
                amount,
                account_number
            )
            
            # Insert with autocommit for each record
            cur.execute("""
                INSERT INTO banking_transactions (
                    transaction_date, description, debit_amount, credit_amount, 
                    balance, account_number, source_file, transaction_hash,
                    created_at, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                row['transaction_date'].date(),
                row['description'],
                row['debit_amount'] if row['debit_amount'] > 0 else None,
                row['credit_amount'] if row['credit_amount'] > 0 else None,
                0,  # balance not provided in these files
                account_number,
                os.path.basename(file_path),
                tx_hash,
                datetime.now(),
                datetime.now()
            ))
            
            # Commit each insert
            cur.connection.commit()
            inserted += 1
            
            if inserted % 1000 == 0:
                print(f"   📈 Processed {inserted} records...")
                
        except psycopg2.IntegrityError as e:
            if 'duplicate key' in str(e).lower():
                # Skip duplicates silently
                cur.connection.rollback()
                continue
            else:
                print(f"[WARN]  Integrity error on row {idx}: {e}")
                errors += 1
                cur.connection.rollback()
        except Exception as e:
            print(f"[WARN]  Error on row {idx}: {e}")
            print(f"    Date: {row['transaction_date']}, Desc: {row['description'][:50]}")
            errors += 1
            cur.connection.rollback()
    
    print(f"[OK] Imported {inserted} transactions")
    if errors > 0:
        print(f"[WARN]  {errors} errors encountered")
    
    return inserted

def check_drina_davis_record(cur):
    """Check if DRINA DAVIS record is present"""
    cur.execute("""
        SELECT COUNT(*) FROM banking_transactions 
        WHERE description ILIKE '%DRINA DAVIS%'
        AND transaction_date >= '2025-06-01'::date
    """)
    count = cur.fetchone()[0]
    
    if count > 0:
        print(f"[OK] Found {count} DRINA DAVIS record(s)")
        
        # Get details
        cur.execute("""
            SELECT transaction_date, description, debit_amount, credit_amount, account_number
            FROM banking_transactions 
            WHERE description ILIKE '%DRINA DAVIS%'
            AND transaction_date >= '2025-06-01'::date
            ORDER BY transaction_date DESC
        """)
        records = cur.fetchall()
        
        for record in records:
            print(f"   📅 {record[0]}: {record[1]} | Debit: {record[2]} | Credit: {record[3]} | Account: {record[4]}")
    else:
        print("[FAIL] DRINA DAVIS record not found")

def main():
    print("🏦 Safe re-import of compiled CIBC banking data...")
    print("=" * 60)
    
    try:
        with psycopg2.connect(**DB_CONFIG) as conn:
            conn.autocommit = False  # We'll handle commits manually
            cur = conn.cursor()
            
            total_imported = 0
            
            for account_id, config in ACCOUNTS.items():
                print(f"\n📋 Processing account {account_id} ({config['account_name']})...")
                
                # Clear existing data for this account
                clear_account_data(cur, config['account_number'])
                conn.commit()
                
                # Import new data
                imported = import_csv_file(
                    cur, 
                    config['file'], 
                    config['account_number'],
                    config['account_name']
                )
                
                total_imported += imported
                
            print(f"\n🎯 Total imported: {total_imported:,} transactions")
            
            # Check for DRINA DAVIS record
            print("\n🔍 Checking for DRINA DAVIS record...")
            check_drina_davis_record(cur)
            
    except Exception as e:
        print(f"[FAIL] Database error: {e}")
        raise

if __name__ == "__main__":
    main()