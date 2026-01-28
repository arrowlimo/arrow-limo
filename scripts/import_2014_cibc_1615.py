#!/usr/bin/env python3
"""
Import 2014 CIBC Account 1615 monthly statement data to database.

Account: 1615 (Business Operating Account)
Branch: #4, 5111 22ND STREET, RED DEER
Data Source: Manual extraction from 2014 CIBC statement PDFs

Monthly data extracted from account summaries:
- Opening/closing balances
- Overdraft interest charges
- Account fees
- Paper statement fees

Data structure: Create opening balance entry, then monthly fee entries,
then closing balance for each month for balance verification.
"""

import sys
import hashlib
import psycopg2
from datetime import datetime
from decimal import Decimal

# Database connection
def get_db_connection():
    return psycopg2.connect(
        host="localhost",
        database="almsdata",
        user="postgres",
        password="***REMOVED***"
    )

# 2014 CIBC 1615 monthly data extracted from statements
MONTHLY_DATA = [
    {'month': 'Jan', 'opening': Decimal('-3499.56'), 'closing': Decimal('-3614.98'), 'overdraft_interest': Decimal('58.24'), 'account_fee': Decimal('50.00'), 'paper_stmt_fee': Decimal('3.00')},
    {'month': 'Feb', 'opening': Decimal('-3614.98'), 'closing': Decimal('-3673.22'), 'overdraft_interest': Decimal('58.24'), 'account_fee': Decimal('50.00'), 'paper_stmt_fee': Decimal('3.00')},
    {'month': 'Mar', 'opening': Decimal('-3673.22'), 'closing': Decimal('-3356.72'), 'overdraft_interest': Decimal('64.27'), 'account_fee': Decimal('50.00'), 'paper_stmt_fee': Decimal('3.00')},
    {'month': 'Apr', 'opening': Decimal('-3356.72'), 'closing': Decimal('-3467.66'), 'overdraft_interest': Decimal('57.94'), 'account_fee': Decimal('50.00'), 'paper_stmt_fee': Decimal('3.00')},
    {'month': 'May', 'opening': Decimal('-3467.66'), 'closing': Decimal('-3582.51'), 'overdraft_interest': Decimal('61.85'), 'account_fee': Decimal('50.00'), 'paper_stmt_fee': Decimal('3.00')},
    {'month': 'Jun', 'opening': Decimal('-3582.51'), 'closing': Decimal('-3697.34'), 'overdraft_interest': Decimal('61.33'), 'account_fee': Decimal('50.00'), 'paper_stmt_fee': Decimal('3.00')},
    {'month': 'Jul', 'opening': Decimal('-3697.34'), 'closing': Decimal('-3816.28'), 'overdraft_interest': Decimal('65.94'), 'account_fee': Decimal('50.00'), 'paper_stmt_fee': Decimal('3.00')},
    {'month': 'Aug', 'opening': Decimal('-3816.28'), 'closing': Decimal('-3937.35'), 'overdraft_interest': Decimal('68.07'), 'account_fee': Decimal('50.00'), 'paper_stmt_fee': Decimal('3.00')},
    {'month': 'Sep', 'opening': Decimal('-3937.35'), 'closing': Decimal('-4005.31'), 'overdraft_interest': Decimal('67.96'), 'account_fee': Decimal('0.00'), 'paper_stmt_fee': Decimal('0.00')},
    {'month': 'Oct', 'opening': Decimal('-4005.31'), 'closing': Decimal('-4076.75'), 'overdraft_interest': Decimal('71.44'), 'account_fee': Decimal('0.00'), 'paper_stmt_fee': Decimal('0.00')},
    {'month': 'Nov', 'opening': Decimal('-4076.75'), 'closing': Decimal('-4147.12'), 'overdraft_interest': Decimal('70.37'), 'account_fee': Decimal('0.00'), 'paper_stmt_fee': Decimal('0.00')},
    {'month': 'Dec', 'opening': Decimal('-4147.12'), 'closing': Decimal('-4221.09'), 'overdraft_interest': Decimal('73.97'), 'account_fee': Decimal('0.00'), 'paper_stmt_fee': Decimal('0.00')},
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

def import_2014_cibc_1615(write=False):
    """Import 2014 CIBC 1615 monthly data."""
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Pre-load existing hashes for account 1615 in 2014
        cur.execute("""
            SELECT source_hash FROM banking_transactions 
            WHERE account_number = '1615'
            AND EXTRACT(YEAR FROM transaction_date) = 2014
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
            opening_date = datetime(2014, month_num, 1)
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
            
            # Monthly fees and charges (last day of month)
            fee_date = datetime(2014, month_num, last_day)
            
            # Overdraft interest
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
            
            # Account fee
            if month_data['account_fee'] > 0:
                af_desc = "ACCOUNT FEE"
                af_hash = generate_hash(fee_date.date(), af_desc, month_data['account_fee'])
                
                if af_hash not in existing_hashes:
                    transactions_to_create.append({
                        'date': fee_date.date(),
                        'description': af_desc,
                        'debit': month_data['account_fee'],
                        'credit': None,
                        'balance': None,
                        'hash': af_hash,
                    })
                    existing_hashes.add(af_hash)
                else:
                    duplicates_skipped += 1
            
            # Paper statement fee
            if month_data['paper_stmt_fee'] > 0:
                psf_desc = "PAPER STMNT FEE"
                psf_hash = generate_hash(fee_date.date(), psf_desc, month_data['paper_stmt_fee'])
                
                if psf_hash not in existing_hashes:
                    transactions_to_create.append({
                        'date': fee_date.date(),
                        'description': psf_desc,
                        'debit': month_data['paper_stmt_fee'],
                        'credit': None,
                        'balance': None,
                        'hash': psf_hash,
                    })
                    existing_hashes.add(psf_hash)
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
    parser = argparse.ArgumentParser(description='Import 2014 CIBC 1615 data')
    parser.add_argument('--write', action='store_true', help='Actually write to database')
    args = parser.parse_args()
    
    success = import_2014_cibc_1615(write=args.write)
    sys.exit(0 if success else 1)
