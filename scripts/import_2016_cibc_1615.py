#!/usr/bin/env python3
"""
Import 2016 CIBC Account 1615 monthly statement data to database.

Account: 1615 (Business Operating Account)
Data Source: Manual extraction from 2016 CIBC statement data (verified)
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
        password="***REDACTED***"
    )

# 2016 CIBC 1615 monthly data
MONTHLY_DATA = [
    {'month': 'Jan', 'opening': Decimal('-5197.99'), 'closing': Decimal('-5290.70'), 'overdraft_interest': Decimal('92.71')},
    {'month': 'Feb', 'opening': Decimal('-5290.70'), 'closing': Decimal('-5378.97'), 'overdraft_interest': Decimal('88.27')},
    {'month': 'Mar', 'opening': Decimal('-5378.97'), 'closing': Decimal('-5474.91'), 'overdraft_interest': Decimal('95.94')},
    {'month': 'Apr', 'opening': Decimal('-5474.91'), 'closing': Decimal('-5569.41'), 'overdraft_interest': Decimal('94.50')},
    {'month': 'May', 'opening': Decimal('-5569.41'), 'closing': Decimal('-5668.74'), 'overdraft_interest': Decimal('99.33')},
    {'month': 'Jun', 'opening': Decimal('-5668.74'), 'closing': Decimal('-5766.58'), 'overdraft_interest': Decimal('97.84')},
    {'month': 'Jul', 'opening': Decimal('-5766.58'), 'closing': Decimal('-5869.43'), 'overdraft_interest': Decimal('102.85')},
    {'month': 'Aug', 'opening': Decimal('-5869.43'), 'closing': Decimal('-5974.11'), 'overdraft_interest': Decimal('104.68')},
    {'month': 'Sep', 'opening': Decimal('-5974.11'), 'closing': Decimal('-6077.22'), 'overdraft_interest': Decimal('103.11')},
    {'month': 'Oct', 'opening': Decimal('-6077.22'), 'closing': Decimal('-6185.61'), 'overdraft_interest': Decimal('108.39')},
    {'month': 'Nov', 'opening': Decimal('-6185.61'), 'closing': Decimal('-6292.38'), 'overdraft_interest': Decimal('106.77')},
    {'month': 'Dec', 'opening': Decimal('-6292.38'), 'closing': Decimal('-6404.61'), 'overdraft_interest': Decimal('112.23')},
]

MONTH_MAP = {
    'Jan': (1, 31), 'Feb': (2, 29), 'Mar': (3, 31), 'Apr': (4, 30),
    'May': (5, 31), 'Jun': (6, 30), 'Jul': (7, 31), 'Aug': (8, 31),
    'Sep': (9, 30), 'Oct': (10, 31), 'Nov': (11, 30), 'Dec': (12, 31),
}

def generate_hash(date, description, amount):
    hash_input = f"{date}|{description}|{amount:.2f}".encode('utf-8')
    return hashlib.sha256(hash_input).hexdigest()

def import_2016_cibc_1615(write=False):
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        cur.execute("""
            SELECT source_hash FROM banking_transactions 
            WHERE account_number = '1615'
            AND EXTRACT(YEAR FROM transaction_date) = 2016
            AND source_hash IS NOT NULL
        """)
        existing_hashes = {row[0] for row in cur.fetchall()}
        
        transactions_to_create = []
        duplicates_skipped = 0
        
        for month_data in MONTHLY_DATA:
            month_name = month_data['month']
            month_num, last_day = MONTH_MAP[month_name]
            
            opening_date = datetime(2016, month_num, 1)
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
            
            fee_date = datetime(2016, month_num, last_day)
            
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
    parser = argparse.ArgumentParser(description='Import 2016 CIBC 1615 data')
    parser.add_argument('--write', action='store_true', help='Actually write to database')
    args = parser.parse_args()
    
    success = import_2016_cibc_1615(write=args.write)
    sys.exit(0 if success else 1)
