#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Import 2014 CIBC statement transactions from CSV with duplicate prevention.
"""
import os
import sys
import csv
import hashlib
import psycopg2
from datetime import datetime
from decimal import Decimal

def get_conn():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        dbname=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REDACTED***')
    )

def parse_date(date_str):
    """Parse 'Jan. 02, 2014' format to date object."""
    # Handle both 'Jan.' and 'January' formats
    date_str = date_str.strip()
    try:
        return datetime.strptime(date_str, '%b. %d, %Y').date()
    except:
        try:
            return datetime.strptime(date_str, '%B %d, %Y').date()
        except:
            print(f"Warning: Could not parse date: {date_str}")
            return None

def generate_hash(date, description, debit, credit):
    """Generate deterministic hash for duplicate detection."""
    hash_input = f"{date}|{description}|{debit:.2f}|{credit:.2f}".encode('utf-8')
    return hashlib.sha256(hash_input).hexdigest()

def main():
    dry_run = '--write' not in sys.argv
    csv_file = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1].endswith('.csv') else 'l:\\limo\\data\\2014_cibc_statement_jan_jun.csv'
    
    conn = get_conn()
    cur = conn.cursor()
    
    print("Importing 2014 CIBC Statement Transactions")
    print("=" * 70)
    
    # Load existing hashes
    cur.execute("""
        SELECT source_hash FROM banking_transactions 
        WHERE account_number = '0228362' 
        AND source_hash IS NOT NULL
    """)
    existing_hashes = {row[0] for row in cur.fetchall()}
    print(f"Loaded {len(existing_hashes)} existing transaction hashes")
    
    # Parse CSV
    transactions = []
    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.reader(f, delimiter='|')
        for row in reader:
            if len(row) != 5:
                continue
            
            date_str, description, debit_str, credit_str, balance_str = row
            date = parse_date(date_str)
            if not date:
                continue
            
            debit = Decimal(debit_str) if debit_str else Decimal('0')
            credit = Decimal(credit_str) if credit_str else Decimal('0')
            balance = Decimal(balance_str) if balance_str else None
            
            source_hash = generate_hash(date, description, debit, credit)
            
            transactions.append({
                'date': date,
                'description': description,
                'debit': debit,
                'credit': credit,
                'balance': balance,
                'hash': source_hash
            })
    
    print(f"Parsed {len(transactions)} transactions from CSV")
    
    # Filter out duplicates
    new_transactions = [t for t in transactions if t['hash'] not in existing_hashes]
    duplicate_count = len(transactions) - len(new_transactions)
    
    print(f"  {len(new_transactions)} new transactions to import")
    print(f"  {duplicate_count} duplicates skipped")
    
    if dry_run:
        print("\n[DRY RUN] Sample transactions to import:")
        for t in new_transactions[:10]:
            print(f"  {t['date']} {t['description'][:50]:50} D:{t['debit']:8.2f} C:{t['credit']:8.2f} Bal:{t['balance']}")
        if len(new_transactions) > 10:
            print(f"  ... and {len(new_transactions) - 10} more")
        print("\nRun with --write to apply import.")
        cur.close()
        conn.close()
        return
    
    # Import new transactions
    print("\n[WRITE MODE] Importing transactions...")
    inserted = 0
    for t in new_transactions:
        cur.execute("""
            INSERT INTO banking_transactions (
                account_number, transaction_date, description,
                debit_amount, credit_amount, balance, source_hash
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, ('0228362', t['date'], t['description'], 
              t['debit'], t['credit'], t['balance'], t['hash']))
        inserted += 1
    
    conn.commit()
    print(f"✓ Imported {inserted} new transactions")
    
    # Verify
    cur.execute("""
        SELECT COUNT(*), 
               COALESCE(SUM(debit_amount), 0),
               COALESCE(SUM(credit_amount), 0),
               MIN(transaction_date),
               MAX(transaction_date)
        FROM banking_transactions
        WHERE account_number = '0228362'
        AND EXTRACT(YEAR FROM transaction_date) = 2014
    """)
    row = cur.fetchone()
    print(f"\nDatabase now has {row[0]} transactions for 2014")
    print(f"  Total debits: ${row[1]:,.2f}")
    print(f"  Total credits: ${row[2]:,.2f}")
    print(f"  Date range: {row[3]} to {row[4]}")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
