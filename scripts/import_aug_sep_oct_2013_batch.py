#!/usr/bin/env python3
"""
Import August, September, October 2013 CIBC banking data - final batch.
August: -$2,731.91 → -$3,061.28
September: -$3,061.28 → -$3,167.12  
October: -$3,167.12 → -$3,276.61
"""

import os
import sys
import psycopg2
import hashlib

ACCOUNT = '0228362'
DRY_RUN = '--write' not in sys.argv

# August 2013 transactions
AUG_2013 = [
    ('2013-08-01', 'DEBIT MEMO MERCH#4017775 GBL MERCH FEES', 138.73, None),
    ('2013-08-01', 'CORRECTION 00339', None, 138.73),
    ('2013-08-01', 'NSF CHARGE 00339', 45.00, None),
    ('2013-08-06', 'DEBIT MEMO REPRESENTED DR GBL MERCH FEES', 138.73, None),
    ('2013-08-06', 'RENT/LEASE 000000000000000 LEASE FINANCE GR', 101.14, None),
    ('2013-08-06', 'CORRECTION 00339', None, 101.14),
    ('2013-08-06', 'CORRECTION 00339', None, 138.73),
    ('2013-08-06', 'NSF CHARGE 00339', 45.00, None),
    ('2013-08-08', 'RENT/LEASE 000000000000000 LEASE FINANCE GR', 202.27, None),
    ('2013-08-08', 'CORRECTION 00339', None, 202.27),
    ('2013-08-08', 'NSF CHARGE 00339', 45.00, None),
    ('2013-08-20', 'RENT/LEASE 000000000000000 LEASE FINANCE GR', 809.12, None),
    ('2013-08-20', 'CORRECTION 00339', None, 809.12),
    ('2013-08-20', 'NSF CHARGE 00339', 45.00, None),
    ('2013-08-23', 'RENT/LEASE 000000000000000 LEASE FINANCE GR', 1618.16, None),
    ('2013-08-23', 'CORRECTION 00339', None, 1618.16),
    ('2013-08-23', 'NSF CHARGE 00339', 45.00, None),
    ('2013-08-30', 'ACCOUNT FEE', 50.00, None),
    ('2013-08-30', 'OVERDRAFT INTEREST', 51.37, None),
    ('2013-08-30', 'PAPER STMT/MT FEE', 3.00, None),
]

# September 2013 transactions
SEP_2013 = [
    ('2013-09-30', 'ACCOUNT FEE', 50.00, None),
    ('2013-09-30', 'OVERDRAFT INTEREST', 52.84, None),
    ('2013-09-30', 'PAPER STMT/MT FEE', 3.00, None),
]

# October 2013 transactions
OCT_2013 = [
    ('2013-10-31', 'ACCOUNT FEE', 50.00, None),
    ('2013-10-31', 'OVERDRAFT INTEREST', 56.49, None),
    ('2013-10-31', 'PAPER STMT/MT FEE', 3.00, None),
]

ALL_TRANSACTIONS = AUG_2013 + SEP_2013 + OCT_2013

def get_conn():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REDACTED***')
    )

def generate_hash(date_str, description, debit, credit):
    """Generate deterministic hash for transaction."""
    hash_input = f"{date_str}|{description}|{debit or 0}|{credit or 0}".encode('utf-8')
    return hashlib.sha256(hash_input).hexdigest()

def main():
    print("\n" + "="*80)
    print("IMPORT AUGUST, SEPTEMBER, OCTOBER 2013 CIBC BANKING DATA - FINAL BATCH")
    print("="*80)
    print(f"Account: {ACCOUNT}")
    print(f"Mode: {'DRY RUN' if DRY_RUN else 'WRITE'}")
    print(f"August transactions: {len(AUG_2013)}")
    print(f"September transactions: {len(SEP_2013)}")
    print(f"October transactions: {len(OCT_2013)}")
    print(f"Total transactions: {len(ALL_TRANSACTIONS)}")
    
    conn = get_conn()
    cur = conn.cursor()
    
    # Check existing data
    cur.execute("""
        SELECT COUNT(*) FROM banking_transactions
        WHERE account_number = %s 
        AND transaction_date >= '2013-08-01' 
        AND transaction_date <= '2013-10-31'
    """, (ACCOUNT,))
    existing_count = cur.fetchone()[0]
    
    print(f"\nExisting Aug-Oct 2013 transactions in DB: {existing_count}")
    
    # Load existing hashes to prevent duplicates
    cur.execute("""
        SELECT source_hash FROM banking_transactions
        WHERE account_number = %s
        AND source_hash IS NOT NULL
    """, (ACCOUNT,))
    existing_hashes = {row[0] for row in cur.fetchall()}
    
    print(f"Loaded {len(existing_hashes)} existing transaction hashes")
    
    # Prepare transactions
    to_import = []
    skipped = []
    
    for txn_date, description, debit, credit in ALL_TRANSACTIONS:
        source_hash = generate_hash(txn_date, description, debit, credit)
        
        if source_hash in existing_hashes:
            skipped.append((txn_date, description, debit, credit))
        else:
            to_import.append((txn_date, description, debit, credit, source_hash))
    
    print(f"\nTo import: {len(to_import)} transactions")
    print(f"Skipped (duplicates): {len(skipped)}")
    
    if len(to_import) == 0:
        print("\n[OK] No new transactions to import")
        cur.close()
        conn.close()
        return
    
    # Calculate totals
    total_debits = sum(t[2] for t in to_import if t[2])
    total_credits = sum(t[3] for t in to_import if t[3])
    
    print(f"\nTotal debits: ${total_debits:,.2f}")
    print(f"Total credits: ${total_credits:,.2f}")
    print(f"Net change: ${total_credits - total_debits:+,.2f}")
    
    if DRY_RUN:
        print("\n[DRY RUN] No changes applied to database.")
        print("Run with --write flag to apply changes.")
        cur.close()
        conn.close()
        return
    
    # Import transactions
    print("\n" + "="*80)
    print("IMPORTING TRANSACTIONS...")
    print("="*80)
    
    imported = 0
    for txn_date, description, debit, credit, source_hash in to_import:
        cur.execute("""
            INSERT INTO banking_transactions (
                account_number, transaction_date, description,
                debit_amount, credit_amount, source_hash
            ) VALUES (%s, %s, %s, %s, %s, %s)
        """, (ACCOUNT, txn_date, description, debit, credit, source_hash))
        imported += 1
    
    conn.commit()
    print(f"\n[SUCCESS] Imported {imported} transactions")
    
    # Verify by month
    for month in ['08', '09', '10']:
        cur.execute("""
            SELECT COUNT(*), SUM(debit_amount), SUM(credit_amount)
            FROM banking_transactions
            WHERE account_number = %s 
            AND EXTRACT(YEAR FROM transaction_date) = 2013
            AND EXTRACT(MONTH FROM transaction_date) = %s
        """, (ACCOUNT, int(month)))
        count, debits, credits = cur.fetchone()
        month_name = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct'][int(month)]
        print(f"{month_name} 2013: {count} txns, ${float(debits or 0):,.2f} debits, ${float(credits or 0):,.2f} credits")
    
    # Final 2013 summary
    cur.execute("""
        SELECT COUNT(*), SUM(debit_amount), SUM(credit_amount)
        FROM banking_transactions
        WHERE account_number = %s 
        AND EXTRACT(YEAR FROM transaction_date) = 2013
    """, (ACCOUNT,))
    total_count, total_debits_db, total_credits_db = cur.fetchone()
    
    print(f"\n{'='*80}")
    print(f"2013 COMPLETE YEAR SUMMARY")
    print(f"{'='*80}")
    print(f"Total 2013 transactions: {total_count}")
    print(f"Total debits: ${float(total_debits_db or 0):,.2f}")
    print(f"Total credits: ${float(total_credits_db or 0):,.2f}")
    print(f"Net change: ${float(total_credits_db or 0) - float(total_debits_db or 0):+,.2f}")
    
    cur.close()
    conn.close()
    
    print("\n" + "="*80)

if __name__ == '__main__':
    main()
