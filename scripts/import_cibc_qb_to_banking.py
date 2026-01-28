#!/usr/bin/env python3
"""
Import missing CIBC QuickBooks reconciliation transactions to banking_transactions.

Imports 353 unmatched transactions identified in comparison.

Created: November 25, 2025
"""

import csv
import psycopg2
import os
import hashlib
from datetime import datetime
import argparse

CSV_PATH = r"l:\limo\data\cibc_qb_reconciliation_consolidated.csv"
ACCOUNT_NUMBER = '0228362'  # CIBC checking

conn = psycopg2.connect(
    host=os.getenv('DB_HOST', 'localhost'),
    database=os.getenv('DB_NAME', 'almsdata'),
    user=os.getenv('DB_USER', 'postgres'),
    password=os.getenv('DB_PASSWORD', '***REMOVED***')
)
cur = conn.cursor()

def create_backup():
    """Create timestamped backup of CIBC banking_transactions."""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_table = f'banking_transactions_cibc_qb_backup_{timestamp}'
    
    print(f"\nCreating backup: {backup_table}")
    cur.execute(f"""
        CREATE TABLE {backup_table} AS
        SELECT * FROM banking_transactions
        WHERE account_number = %s
    """, (ACCOUNT_NUMBER,))
    
    cur.execute(f"SELECT COUNT(*) FROM {backup_table}")
    count = cur.fetchone()[0]
    print(f"   Backed up: {count} rows")
    
    return backup_table

def load_csv_transactions():
    """Load CSV transactions."""
    print(f"\nLoading CSV: {CSV_PATH}")
    transactions = []
    
    with open(CSV_PATH, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            transactions.append({
                'date': datetime.strptime(row['date'], '%Y-%m-%d').date(),
                'type': row['type'],
                'num': row['num'],
                'name': row['name'],
                'amount': float(row['amount']),
                'balance': float(row['balance'])
            })
    
    print(f"   Loaded: {len(transactions)} transactions")
    return transactions

def find_unmatched(csv_transactions):
    """Find CSV transactions not in database."""
    print(f"\nFinding unmatched transactions...")
    
    # Build database lookup
    cur.execute("""
        SELECT transaction_date, debit_amount, credit_amount
        FROM banking_transactions
        WHERE account_number = %s
    """, (ACCOUNT_NUMBER,))
    
    db_lookup = set()
    for row in cur.fetchall():
        date = row[0]
        debit = float(row[1]) if row[1] else 0.0
        credit = float(row[2]) if row[2] else 0.0
        amount = abs(debit - credit)
        db_lookup.add((date, amount))
    
    print(f"   Database has {len(db_lookup)} unique date+amount combinations")
    
    # Find unmatched
    unmatched = []
    for txn in csv_transactions:
        amount = abs(txn['amount'])
        key = (txn['date'], amount)
        
        if key not in db_lookup:
            unmatched.append(txn)
    
    print(f"   Unmatched: {len(unmatched)} transactions")
    return unmatched

def import_transactions(transactions, dry_run=True):
    """Import unmatched transactions."""
    print(f"\n{'DRY RUN: ' if dry_run else ''}Importing {len(transactions)} transactions...")
    
    imported = 0
    skipped = 0
    
    for txn in transactions:
        # Generate hash for deduplication
        hash_input = f"{txn['date']}|{txn['type']}|{txn['name']}|{txn['amount']:.2f}"
        source_hash = hashlib.sha256(hash_input.encode('utf-8')).hexdigest()
        
        # Determine debit/credit from amount
        if txn['amount'] < 0:
            debit_amount = abs(txn['amount'])
            credit_amount = None
        else:
            debit_amount = None
            credit_amount = txn['amount']
        
        # Build description from type, num, name
        description = f"{txn['type']}"
        if txn['num'] and txn['num'] != '-':
            description += f" #{txn['num']}"
        if txn['name']:
            description += f" {txn['name']}"
        
        # Check if already exists by hash
        cur.execute("""
            SELECT COUNT(*) FROM banking_transactions
            WHERE source_hash = %s
        """, (source_hash,))
        
        if cur.fetchone()[0] > 0:
            skipped += 1
            continue
        
        if not dry_run:
            # Insert transaction
            cur.execute("""
                INSERT INTO banking_transactions (
                    account_number,
                    transaction_date,
                    description,
                    debit_amount,
                    credit_amount,
                    balance,
                    source_hash
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                ACCOUNT_NUMBER,
                txn['date'],
                description,
                debit_amount,
                credit_amount,
                txn['balance'],
                source_hash
            ))
        
        imported += 1
        
        if (imported + skipped) % 50 == 0:
            print(f"   Processed {imported + skipped}/{len(transactions)}...")
    
    print(f"\n   Imported: {imported}")
    print(f"   Skipped (duplicates): {skipped}")
    
    return imported

def main():
    parser = argparse.ArgumentParser(description='Import CIBC QB reconciliation data')
    parser.add_argument('--write', action='store_true', help='Actually write to database')
    args = parser.parse_args()
    
    print("="*80)
    print("IMPORT CIBC QB RECONCILIATION TO DATABASE")
    print("="*80)
    print(f"Mode: {'WRITE' if args.write else 'DRY RUN'}")
    
    # Load CSV
    csv_transactions = load_csv_transactions()
    
    # Find unmatched
    unmatched = find_unmatched(csv_transactions)
    
    if not unmatched:
        print("\n✓ No unmatched transactions to import!")
        cur.close()
        conn.close()
        return
    
    # Create backup
    if args.write:
        backup_table = create_backup()
    
    # Import
    imported = import_transactions(unmatched, dry_run=not args.write)
    
    # Commit
    if args.write:
        conn.commit()
        print(f"\n✓ Changes committed to database")
        print(f"✓ Backup: {backup_table}")
    else:
        conn.rollback()
        print(f"\nDRY RUN - No changes made")
        print(f"Run with --write to apply changes")
    
    # Verify
    if args.write:
        cur.execute("""
            SELECT COUNT(*) FROM banking_transactions
            WHERE account_number = %s
        """, (ACCOUNT_NUMBER,))
        total = cur.fetchone()[0]
        print(f"\nFinal CIBC transaction count: {total}")
    
    print("\n" + "="*80)
    print("COMPLETE")
    print("="*80)
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
