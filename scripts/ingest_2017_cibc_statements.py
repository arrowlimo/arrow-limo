#!/usr/bin/env python3
"""
Ingest 2017 CIBC bank statements from Excel files into banking_transactions.

Strategy:
1. Read all Excel files in L:\\limo\\2017 cibc\\
2. Parse transaction records (date, description, debit, credit)
3. Compare against existing banking_transactions for 2017
4. Insert missing records with deduplication (date+description+amount hash)
"""

import os
import sys
import psycopg2
import pandas as pd
import hashlib
from datetime import datetime
from pathlib import Path

DB = dict(
    host=os.getenv('DB_HOST', 'localhost'),
    database=os.getenv('DB_NAME', 'almsdata'),
    user=os.getenv('DB_USER', 'postgres'),
    password=os.getenv('DB_PASSWORD', '***REDACTED***'),
)

SOURCE_DIR = Path(r'L:\limo\2017 cibc')
ACCOUNT_NUMBER = '3648117'  # Default CIBC account


def parse_cibc_excel(file_path):
    """Parse CIBC Excel format: date, description, debit, credit columns (no header)."""
    df = pd.read_excel(file_path, header=None)
    
    # Expected format: col0=date, col1=description, col2=debit, col3=credit
    # Skip rows until we find dates
    transactions = []
    
    for idx, row in df.iterrows():
        try:
            # Try to parse first column as date
            if pd.isna(row[0]):
                continue
            
            trans_date = pd.to_datetime(row[0])
            if trans_date.year != 2017:
                continue
            
            description = str(row[1]) if not pd.isna(row[1]) else ''
            if not description or description == 'nan':
                continue
            
            debit = float(row[2]) if not pd.isna(row[2]) else 0.0
            credit = float(row[3]) if not pd.isna(row[3]) else 0.0
            
            transactions.append({
                'transaction_date': trans_date.date(),
                'description': description.strip(),
                'debit_amount': debit,
                'credit_amount': credit,
                'source_file': file_path.name,
            })
        except (ValueError, TypeError, KeyError):
            continue
    
    return transactions


def generate_hash(date, desc, debit, credit):
    """Generate hash for deduplication."""
    key = f"{date}|{desc}|{debit:.2f}|{credit:.2f}"
    return hashlib.sha256(key.encode()).hexdigest()[:16]


def get_existing_hashes(cur, year=2017):
    """Get existing transaction hashes from database."""
    cur.execute("""
        SELECT transaction_hash
        FROM banking_transactions
        WHERE EXTRACT(YEAR FROM transaction_date) = %s
          AND transaction_hash IS NOT NULL
    """, (year,))
    return {row[0] for row in cur.fetchall()}


def main():
    print("INGESTING 2017 CIBC BANK STATEMENTS")
    print("=" * 80)
    
    # Find all Excel files
    excel_files = list(SOURCE_DIR.glob('*.xlsx'))
    print(f"\nFound {len(excel_files)} Excel files in {SOURCE_DIR}")
    
    all_transactions = []
    for file_path in excel_files:
        print(f"\nParsing: {file_path.name}")
        transactions = parse_cibc_excel(file_path)
        print(f"  Found {len(transactions)} transactions")
        all_transactions.extend(transactions)
    
    print(f"\n Total transactions parsed: {len(all_transactions)}")
    
    if not all_transactions:
        print("No transactions found. Exiting.")
        return
    
    # Connect to database
    with psycopg2.connect(**DB) as conn:
        with conn.cursor() as cur:
            # Get existing hashes
            existing_hashes = get_existing_hashes(cur, 2017)
            print(f"Existing 2017 transactions in DB: {len(existing_hashes)}")
            
            # Filter out duplicates
            new_transactions = []
            for trans in all_transactions:
                trans_hash = generate_hash(
                    trans['transaction_date'],
                    trans['description'],
                    trans['debit_amount'],
                    trans['credit_amount']
                )
                trans['transaction_hash'] = trans_hash
                
                if trans_hash not in existing_hashes:
                    new_transactions.append(trans)
            
            print(f"New transactions to insert: {len(new_transactions)}")
            
            if not new_transactions:
                print("\nNo new transactions to insert. All records already exist.")
                return
            
            # Show sample
            print(f"\nSample of new transactions (first 5):")
            for trans in new_transactions[:5]:
                print(f"  {trans['transaction_date']}  debit ${trans['debit_amount']:.2f}  credit ${trans['credit_amount']:.2f}")
                print(f"    {trans['description'][:100]}")
            
            # Confirm before insert
            response = input(f"\nInsert {len(new_transactions)} new transactions? (yes/no): ")
            if response.lower() != 'yes':
                print("Cancelled.")
                return
            
            # Insert new transactions
            inserted_count = 0
            skipped_count = 0
            for trans in new_transactions:
                try:
                    # Check if already exists (transaction_hash may not have unique constraint)
                    cur.execute("""
                        SELECT transaction_id FROM banking_transactions
                        WHERE transaction_hash = %s
                    """, (trans['transaction_hash'],))
                    
                    if cur.fetchone():
                        skipped_count += 1
                        continue
                    
                    cur.execute("""
                        INSERT INTO banking_transactions (
                            account_number, transaction_date, description,
                            debit_amount, credit_amount, source_file, transaction_hash,
                            import_batch
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        RETURNING transaction_id
                    """, (
                        ACCOUNT_NUMBER,
                        trans['transaction_date'],
                        trans['description'],
                        trans['debit_amount'],
                        trans['credit_amount'],
                        trans['source_file'],
                        trans['transaction_hash'],
                        '2017-cibc-manual-ingest'
                    ))
                    
                    result = cur.fetchone()
                    if result:
                        inserted_count += 1
                        if inserted_count % 50 == 0:
                            print(f"  Inserted {inserted_count}...")
                
                except psycopg2.IntegrityError as e:
                    print(f"  Error: {trans['transaction_date']} {trans['description'][:50]} - {e}")
                    skipped_count += 1
                    continue
            
            conn.commit()
            print(f"\n[OK] Successfully inserted {inserted_count} new transactions")
            print(f"Skipped {skipped_count} duplicates")
            print(f"Import batch: 2017-cibc-manual-ingest")


if __name__ == '__main__':
    main()
