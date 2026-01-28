#!/usr/bin/env python3
"""
Import new CIBC transaction CSV files to update banking_transactions table.
Handles three account files with different formats and prevents duplicates.
"""

import csv
import psycopg2
import os
from datetime import datetime
from dotenv import load_dotenv
import hashlib

load_dotenv()

# Account mapping based on file names
ACCOUNT_MAPPING = {
    'cibc811sept7.csv': '3648117',      # Business Deposit
    'cibc8362sept13.csv': '0228362',    # Checking Account  
    'cibc14462.csv': '8314462'          # Vehicle Loans
}

def generate_transaction_hash(date, description, debit_amount, credit_amount, account_number):
    """Generate unique hash for duplicate detection."""
    hash_string = f"{date}|{description}|{debit_amount or ''}|{credit_amount or ''}|{account_number}"
    return hashlib.md5(hash_string.encode()).hexdigest()

def parse_cibc_csv(file_path, account_number):
    """Parse CIBC CSV file and return list of transaction records."""
    transactions = []
    
    print(f"Processing {file_path} for account {account_number}")
    
    with open(file_path, 'r', encoding='utf-8') as file:
        reader = csv.reader(file)
        row_count = 0
        
        for row in reader:
            row_count += 1
            if len(row) < 3:
                continue
                
            try:
                # Parse date (YYYY-MM-DD format)
                transaction_date = datetime.strptime(row[0].strip(), '%Y-%m-%d').date()
                description = row[1].strip()
                
                # Parse amounts - handle empty strings
                debit_amount = None
                credit_amount = None
                
                if len(row) >= 3 and row[2].strip():
                    debit_amount = float(row[2].strip())
                    
                if len(row) >= 4 and row[3].strip():
                    credit_amount = float(row[3].strip())
                
                # Generate transaction hash for duplicate detection
                transaction_hash = generate_transaction_hash(
                    transaction_date, description, debit_amount, credit_amount, account_number
                )
                
                transactions.append({
                    'account_number': account_number,
                    'transaction_date': transaction_date,
                    'description': description,
                    'debit_amount': debit_amount,
                    'credit_amount': credit_amount,
                    'transaction_hash': transaction_hash,
                    'source_file': os.path.basename(file_path)
                })
                
            except Exception as e:
                print(f"Error parsing row {row_count} in {file_path}: {e}")
                print(f"Row data: {row}")
                continue
    
    print(f"Parsed {len(transactions)} transactions from {file_path}")
    return transactions

def import_transactions(transactions):
    """Import transactions to database, skipping duplicates."""
    conn = psycopg2.connect(
        host=os.getenv('DB_HOST'),
        port=os.getenv('DB_PORT'),
        database=os.getenv('DB_NAME'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD')
    )
    
    cursor = conn.cursor()
    
    inserted_count = 0
    duplicate_count = 0
    
    for txn in transactions:
        try:
            # Check if transaction already exists
            cursor.execute(
                "SELECT transaction_id FROM banking_transactions WHERE transaction_hash = %s",
                (txn['transaction_hash'],)
            )
            
            if cursor.fetchone():
                duplicate_count += 1
                continue
            
            # Insert new transaction
            cursor.execute("""
                INSERT INTO banking_transactions (
                    account_number, transaction_date, description, 
                    debit_amount, credit_amount, transaction_hash,
                    created_at, updated_at
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, NOW(), NOW()
                )
            """, (
                txn['account_number'],
                txn['transaction_date'],
                txn['description'],
                txn['debit_amount'],
                txn['credit_amount'],
                txn['transaction_hash']
            ))
            
            inserted_count += 1
            
        except Exception as e:
            print(f"Error inserting transaction: {e}")
            print(f"Transaction: {txn}")
            conn.rollback()
            continue
    
    conn.commit()
    cursor.close()
    conn.close()
    
    print(f"Import complete: {inserted_count} new transactions, {duplicate_count} duplicates skipped")
    return inserted_count, duplicate_count

def main():
    """Main import process."""
    base_path = r"L:\limo\CIBC UPLOADS\3648117 (CIBC Business Deposit account, alias for 0534"
    
    files_to_import = [
        'cibc811sept7.csv',      # Business Deposit (3648117)
        'cibc8362sept13.csv',    # Checking (0228362)
        'cibc14462.csv'          # Vehicle Loans (8314462)
    ]
    
    all_transactions = []
    
    # Parse all files
    for filename in files_to_import:
        file_path = os.path.join(base_path, filename)
        account_number = ACCOUNT_MAPPING[filename]
        
        if os.path.exists(file_path):
            transactions = parse_cibc_csv(file_path, account_number)
            all_transactions.extend(transactions)
        else:
            print(f"Warning: File not found: {file_path}")
    
    if all_transactions:
        print(f"\nTotal transactions to import: {len(all_transactions)}")
        
        # Sort by date for better organization
        all_transactions.sort(key=lambda x: x['transaction_date'])
        
        # Show date range
        min_date = min(txn['transaction_date'] for txn in all_transactions)
        max_date = max(txn['transaction_date'] for txn in all_transactions)
        print(f"Date range: {min_date} to {max_date}")
        
        # Import to database
        inserted, duplicates = import_transactions(all_transactions)
        
        print(f"\n[OK] Import Summary:")
        print(f"   New transactions: {inserted}")
        print(f"   Duplicates skipped: {duplicates}")
        print(f"   Total processed: {len(all_transactions)}")
        
    else:
        print("No transactions found to import.")

if __name__ == '__main__':
    main()