#!/usr/bin/env python3
"""
Import 2015 CIBC Account 1615 monthly statement data to database.

Account: 1615 (Business Operating Account)
Branch: #4, 5111 22ND STREET, RED DEER
Data Source: Manual extraction from 2015 CIBC statement data (verified from QA backup)

Monthly data: Overdraft interest charges only (minimal activity)
"""

import sys
import hashlib
import psycopg2
from datetime import datetime
from decimal import Decimal

def get_db_connection():
    return psycopg2.connect(
        host="localhost",
        database="almsdata",
        user="postgres",
        password="***REMOVED***"
    )

# 2015 CIBC 1615 monthly data extracted from verified statements
MONTHLY_DATA = [
    {'month': 'Jan', 'opening': Decimal('-4221.09'), 'closing': Decimal('-4296.38'), 'overdraft_interest': Decimal('75.29')},
    {'month': 'Feb', 'opening': Decimal('-4296.38'), 'closing': Decimal('-4365.59'), 'overdraft_interest': Decimal('69.21')},
    {'month': 'Mar', 'opening': Decimal('-4365.59'), 'closing': Decimal('-4443.45'), 'overdraft_interest': Decimal('77.86')},
    {'month': 'Apr', 'opening': Decimal('-4443.45'), 'closing': Decimal('-4520.14'), 'overdraft_interest': Decimal('76.69')},
    {'month': 'May', 'opening': Decimal('-4520.14'), 'closing': Decimal('-4600.76'), 'overdraft_interest': Decimal('80.62')},
    {'month': 'Jun', 'opening': Decimal('-4600.76'), 'closing': Decimal('-4680.17'), 'overdraft_interest': Decimal('79.41')},
    {'month': 'Jul', 'opening': Decimal('-4680.17'), 'closing': Decimal('-4763.64'), 'overdraft_interest': Decimal('83.47')},
    {'month': 'Aug', 'opening': Decimal('-4763.64'), 'closing': Decimal('-4848.60'), 'overdraft_interest': Decimal('84.96')},
    {'month': 'Sep', 'opening': Decimal('-4848.60'), 'closing': Decimal('-4932.29'), 'overdraft_interest': Decimal('83.69')},
    {'month': 'Oct', 'opening': Decimal('-4932.29'), 'closing': Decimal('-5020.26'), 'overdraft_interest': Decimal('87.97')},
    {'month': 'Nov', 'opening': Decimal('-5020.26'), 'closing': Decimal('-5106.91'), 'overdraft_interest': Decimal('86.65')},
    {'month': 'Dec', 'opening': Decimal('-5106.91'), 'closing': Decimal('-5197.99'), 'overdraft_interest': Decimal('91.08')},
]

MONTH_MAP = {
    'Jan': (1, 31), 'Feb': (2, 28), 'Mar': (3, 31), 'Apr': (4, 30),
    'May': (5, 31), 'Jun': (6, 30), 'Jul': (7, 31), 'Aug': (8, 31),
    'Sep': (9, 30), 'Oct': (10, 31), 'Nov': (11, 30), 'Dec': (12, 31),
}

def generate_hash(date, description, amount):
    """Generate SHA256 hash for deduplication."""
    hash_input = f"{date}|{description}|{amount:.2f}".encode('utf-8')
    return hashlib.sha256(hash_input).hexdigest()

def import_2015_cibc_1615(write=False):
    """Import 2015 CIBC 1615 monthly data."""
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Pre-load existing hashes for account 1615 in 2015
        cur.execute("""
            SELECT source_hash FROM banking_transactions 
            WHERE account_number = '1615'
            AND EXTRACT(YEAR FROM transaction_date) = 2015
            AND source_hash IS NOT NULL
        """)
        existing_hashes = {row[0] for row in cur.fetchall()}
        
        transactions_to_create = []
        duplicates_skipped = 0
        
        # Process each month
        for month_data in MONTHLY_DATA:
            month_name = month_data['month']
            month_num, last_day = MONTH_MAP[month_name]
            
            # Opening balance entry (first day of month)
            opening_date = datetime(2015, month_num, 1)
            opening_desc = "Opening balance"
            opening_hash = generate_hash(opening_date.date(), opening_desc, month_data['opening'])
            
            if opening_hash not in existing_hashes:
                transactions_to_create.append({
                    'date': opening_date.date(),
                    'description': opening_desc,
                    'debit': None,
                    'credit': None,
                    'balance': month_data['opening'],
                    'hash': opening_hash,
                })
                existing_hashes.add(opening_hash)
            else:
                duplicates_skipped += 1
            
            # Overdraft interest (last day of month)
            fee_date = datetime(2015, month_num, last_day)
            
            if month_data['overdraft_interest'] > 0:
                oi_desc = "OVERDRAFT INTEREST"
                oi_hash = generate_hash(fee_date.date(), oi_desc, month_data['overdraft_interest'])
                
                if oi_hash not in existing_hashes:
                    transactions_to_create.append({
                        'date': fee_date.date(),
                        'description': oi_desc,
                        'debit': month_data['overdraft_interest'],
                        'credit': None,
                        'balance': None,
                        'hash': oi_hash,
                    })
                    existing_hashes.add(oi_hash)
                else:
                    duplicates_skipped += 1
            
            # Closing balance entry (last day of month)
            closing_desc = "Closing balance"
            closing_hash = generate_hash(fee_date.date(), closing_desc, month_data['closing'])
            
            if closing_hash not in existing_hashes:
                transactions_to_create.append({
                    'date': fee_date.date(),
                    'description': closing_desc,
                    'debit': None,
                    'credit': None,
                    'balance': month_data['closing'],
                    'hash': closing_hash,
                })
                existing_hashes.add(closing_hash)
            else:
                duplicates_skipped += 1
        
        print(f"Ready: {len(transactions_to_create)} transactions to create")
        print(f"Skipping: {duplicates_skipped} existing duplicates")
        
        if write:
            # Insert all transactions
            for txn in transactions_to_create:
                cur.execute("""
                    INSERT INTO banking_transactions (
                        account_number, transaction_date, description,
                        debit_amount, credit_amount, balance, source_hash
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (
                    '1615',
                    txn['date'],
                    txn['description'],
                    txn['debit'],
                    txn['credit'],
                    txn['balance'],
                    txn['hash'],
                ))
            
            conn.commit()
            print(f"✓ Successfully imported {len(transactions_to_create)} transactions")
            print(f"✓ Skipped {duplicates_skipped} existing duplicates")
        else:
            conn.rollback()
            print("\nSample transactions that would be created:")
            for i, txn in enumerate(transactions_to_create[:5]):
                print(f"  {txn['date']} | {txn['description']:<30} | Bal:{txn['balance']}")
            if len(transactions_to_create) > 5:
                print(f"  ... ({len(transactions_to_create) - 5} more)")
    
    except Exception as e:
        conn.rollback()
        print(f"✗ Error: {e}", file=sys.stderr)
        return False
    finally:
        cur.close()
        conn.close()
    
    return True

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Import 2015 CIBC 1615 data')
    parser.add_argument('--write', action='store_true', help='Actually write to database')
    args = parser.parse_args()
    
    success = import_2015_cibc_1615(write=args.write)
    sys.exit(0 if success else 1)
