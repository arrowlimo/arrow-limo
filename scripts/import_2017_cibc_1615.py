#!/usr/bin/env python3
"""
Import 2017 CIBC Account 1615 monthly statement data to database.

Account: 1615 (Business Operating Account)
Data Source: Manual extraction from 2017 CIBC statement data (verified)
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

# 2017 CIBC 1615 monthly data
MONTHLY_DATA = [
    {'month': 'Jan', 'opening': Decimal('-6404.61'), 'closing': Decimal('-6518.84'), 'overdraft_interest': Decimal('114.23')},
    {'month': 'Feb', 'opening': Decimal('-6518.84'), 'closing': Decimal('-6623.86'), 'overdraft_interest': Decimal('105.02')},
    {'month': 'Mar', 'opening': Decimal('-6623.86'), 'closing': Decimal('-6742.00'), 'overdraft_interest': Decimal('118.14')},
    {'month': 'Apr', 'opening': Decimal('-6742.00'), 'closing': Decimal('-6858.37'), 'overdraft_interest': Decimal('116.37')},
    {'month': 'May', 'opening': Decimal('-6858.37'), 'closing': Decimal('-6980.69'), 'overdraft_interest': Decimal('122.32')},
    {'month': 'Jun', 'opening': Decimal('-6980.69'), 'closing': Decimal('-7101.18'), 'overdraft_interest': Decimal('120.49')},
    {'month': 'Jul', 'opening': Decimal('-7101.18'), 'closing': Decimal('-7227.83'), 'overdraft_interest': Decimal('126.65')},
    {'month': 'Aug', 'opening': Decimal('-7227.83'), 'closing': Decimal('-7356.74'), 'overdraft_interest': Decimal('128.91')},
    {'month': 'Sep', 'opening': Decimal('-7356.74'), 'closing': Decimal('-7483.72'), 'overdraft_interest': Decimal('126.98')},
    {'month': 'Oct', 'opening': Decimal('-7483.72'), 'closing': Decimal('-7620.75'), 'overdraft_interest': Decimal('137.03')},  # Oct has fee on Oct 6 (3.50) + Oct 31 (133.53)
    {'month': 'Nov', 'opening': Decimal('-7620.75'), 'closing': Decimal('-7752.29'), 'overdraft_interest': Decimal('131.54')},
    {'month': 'Dec', 'opening': Decimal('-7752.29'), 'closing': Decimal('-7890.56'), 'overdraft_interest': Decimal('138.27')},
]

MONTH_MAP = {
    'Jan': (1, 31), 'Feb': (2, 28), 'Mar': (3, 31), 'Apr': (4, 30),
    'May': (5, 31), 'Jun': (6, 30), 'Jul': (7, 31), 'Aug': (8, 31),
    'Sep': (9, 30), 'Oct': (10, 31), 'Nov': (11, 30), 'Dec': (12, 31),
}

def generate_hash(date, description, amount):
    hash_input = f"{date}|{description}|{amount:.2f}".encode('utf-8')
    return hashlib.sha256(hash_input).hexdigest()

def import_2017_cibc_1615(write=False):
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        cur.execute("""
            SELECT source_hash FROM banking_transactions 
            WHERE account_number = '1615'
            AND EXTRACT(YEAR FROM transaction_date) = 2017
            AND source_hash IS NOT NULL
        """)
        existing_hashes = {row[0] for row in cur.fetchall()}
        
        transactions_to_create = []
        duplicates_skipped = 0
        
        for month_data in MONTHLY_DATA:
            month_name = month_data['month']
            month_num, last_day = MONTH_MAP[month_name]
            
            opening_date = datetime(2017, month_num, 1)
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
            
            fee_date = datetime(2017, month_num, last_day)
            
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
    parser = argparse.ArgumentParser(description='Import 2017 CIBC 1615 data')
    parser.add_argument('--write', action='store_true', help='Actually write to database')
    args = parser.parse_args()
    
    success = import_2017_cibc_1615(write=args.write)
    sys.exit(0 if success else 1)
