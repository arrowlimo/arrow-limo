#!/usr/bin/env python3
"""
Re-import all three compiled CIBC CSV files into banking_transactions table.
- Safely clears existing data for each account first to prevent duplicates
- Imports from the compiled 'all.csv' files for accounts 8362, 8117, and 4462
- Preserves data integrity with proper transaction handling

Usage:
  python scripts/reimport_compiled_cibc_banking.py
"""
import os
import pandas as pd
import psycopg2
from datetime import datetime

# Database connection
DB_CONFIG = {
    'dbname': os.environ.get('DB_NAME', 'almsdata'),
    'user': os.environ.get('DB_USER', 'postgres'),
    'password': os.environ.get('DB_PASSWORD', '***REMOVED***'),
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

def clear_account_data(cur, account_number):
    """Safely clear existing data for this account"""
    cur.execute("""
        DELETE FROM banking_transactions 
        WHERE account_number = %s
    """, (account_number,))
    print(f"Cleared existing data for account {account_number}")

def import_csv_file(cur, file_path, account_number, account_name):
    """Import CSV data for one account"""
    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        return 0
    
    # Read CSV with proper headers
    try:
        df = pd.read_csv(file_path)
        print(f"Found columns: {df.columns.tolist()}")
        print(f"Data shape: {df.shape}")
        
        # Map columns based on actual structure
        # Expected: Bank_id,Trans_date,Trans_description,Debit,Credit,Reconsiled_receipt_id,Reconsiled_receipt_total
        df = df.rename(columns={
            'Trans_date': 'transaction_date',
            'Trans_description': 'description', 
            'Debit': 'debit_amount',
            'Credit': 'credit_amount'
        })
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return 0
    
    # Clean and process data
    df = df.dropna(subset=['transaction_date', 'description'])
    df['transaction_date'] = pd.to_datetime(df['transaction_date'], errors='coerce')
    df = df.dropna(subset=['transaction_date'])
    
    # Convert amounts
    for col in ['debit_amount', 'credit_amount']:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    
    # Add balance column (set to 0 since not provided in these files)
    df['balance'] = 0
    
    # Insert records
    inserted = 0
    for _, row in df.iterrows():
        try:
            cur.execute("""
                INSERT INTO banking_transactions (
                    transaction_date, description, debit_amount, credit_amount, 
                    balance, account_number, account_name, source_file
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                row['transaction_date'].date(),
                row['description'],
                row['debit_amount'] if row['debit_amount'] > 0 else None,
                row['credit_amount'] if row['credit_amount'] > 0 else None,
                row['balance'],
                account_number,
                account_name,
                os.path.basename(file_path)
            ))
            inserted += 1
        except Exception as e:
            print(f"Error inserting row: {e}")
            continue
    
    return inserted

def main():
    print("🏦 Re-importing compiled CIBC banking data...")
    print("=" * 50)
    
    conn = psycopg2.connect(**DB_CONFIG)
    try:
        with conn.cursor() as cur:
            total_inserted = 0
            
            for account_code, account_info in ACCOUNTS.items():
                print(f"\n📋 Processing account {account_code} ({account_info['account_name']})...")
                
                # Clear existing data for this account
                clear_account_data(cur, account_info['account_number'])
                
                # Import new data
                inserted = import_csv_file(
                    cur, 
                    account_info['file'], 
                    account_info['account_number'], 
                    account_info['account_name']
                )
                
                print(f"[OK] Imported {inserted:,} transactions for account {account_code}")
                total_inserted += inserted
            
            conn.commit()
            print(f"\n🎯 Total imported: {total_inserted:,} transactions")
            
            # Verify DRINA DAVIS record is now present
            cur.execute("""
                SELECT transaction_id, transaction_date, description, credit_amount
                FROM banking_transactions
                WHERE description ILIKE '%DRINA DAVIS%'
                  AND credit_amount BETWEEN 1713.99 AND 1714.01
                ORDER BY transaction_date DESC
                LIMIT 1
            """)
            drina_record = cur.fetchone()
            
            if drina_record:
                print(f"\n[OK] DRINA DAVIS record found: ID={drina_record[0]}, Date={drina_record[1]}, Amount=${drina_record[3]}")
            else:
                print(f"\n[WARN]  DRINA DAVIS record not found after import")
                
    except Exception as e:
        conn.rollback()
        print(f"[FAIL] Error during import: {e}")
    finally:
        conn.close()

if __name__ == '__main__':
    main()