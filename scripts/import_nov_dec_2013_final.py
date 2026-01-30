#!/usr/bin/env python3
"""
Import November and December 2013 CIBC banking data - COMPLETE 2013!
November: -$3,276.61 → -$3,386.17
December: -$3,386.17 → -$3,499.56
"""

import os
import sys
import psycopg2
import hashlib

ACCOUNT = '0228362'
DRY_RUN = '--write' not in sys.argv

# November 2013 transactions
NOV_2013 = [
    ('2013-11-29', 'ACCOUNT FEE', 50.00, None),
    ('2013-11-29', 'OVERDRAFT INTEREST', 56.56, None),
    ('2013-11-29', 'PAPER STMT/MT FEE', 3.00, None),
]

# December 2013 transactions
DEC_2013 = [
    ('2013-12-31', 'ACCOUNT FEE', 50.00, None),
    ('2013-12-31', 'OVERDRAFT INTEREST', 60.39, None),
    ('2013-12-31', 'PAPER STMT/MT FEE', 3.00, None),
]

ALL_TRANSACTIONS = NOV_2013 + DEC_2013

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
    print("IMPORT NOVEMBER & DECEMBER 2013 - COMPLETE 2013 YEAR!")
    print("="*80)
    print(f"Account: {ACCOUNT}")
    print(f"Mode: {'DRY RUN' if DRY_RUN else 'WRITE'}")
    print(f"November transactions: {len(NOV_2013)}")
    print(f"December transactions: {len(DEC_2013)}")
    print(f"Total transactions: {len(ALL_TRANSACTIONS)}")
    
    conn = get_conn()
    cur = conn.cursor()
    
    # Check existing data
    cur.execute("""
        SELECT COUNT(*) FROM banking_transactions
        WHERE account_number = %s 
        AND transaction_date >= '2013-11-01' 
        AND transaction_date <= '2013-12-31'
    """, (ACCOUNT,))
    existing_count = cur.fetchone()[0]
    
    print(f"\nExisting Nov-Dec 2013 transactions in DB: {existing_count}")
    
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
    for month in ['11', '12']:
        cur.execute("""
            SELECT COUNT(*), SUM(debit_amount), SUM(credit_amount)
            FROM banking_transactions
            WHERE account_number = %s 
            AND EXTRACT(YEAR FROM transaction_date) = 2013
            AND EXTRACT(MONTH FROM transaction_date) = %s
        """, (ACCOUNT, int(month)))
        count, debits, credits = cur.fetchone()
        month_name = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'][int(month)]
        print(f"{month_name} 2013: {count} txns, ${float(debits or 0):,.2f} debits, ${float(credits or 0):,.2f} credits")
    
    # Final 2013 COMPLETE summary
    cur.execute("""
        SELECT COUNT(*), 
               MIN(transaction_date), 
               MAX(transaction_date),
               SUM(debit_amount), 
               SUM(credit_amount)
        FROM banking_transactions
        WHERE account_number = %s 
        AND EXTRACT(YEAR FROM transaction_date) = 2013
    """, (ACCOUNT,))
    total_count, first_date, last_date, total_debits_db, total_credits_db = cur.fetchone()
    
    print(f"\n{'='*80}")
    print(f"🎉 2013 COMPLETE YEAR - FINAL SUMMARY 🎉")
    print(f"{'='*80}")
    print(f"Total 2013 transactions: {total_count}")
    print(f"Date range: {first_date} to {last_date}")
    print(f"Total debits: ${float(total_debits_db or 0):,.2f}")
    print(f"Total credits: ${float(total_credits_db or 0):,.2f}")
    print(f"Net change: ${float(total_credits_db or 0) - float(total_debits_db or 0):+,.2f}")
    print(f"\n✓ 2013 CIBC account 0228362 banking data is now COMPLETE!")
    
    cur.close()
    conn.close()
    
    print("\n" + "="*80)

if __name__ == '__main__':
    main()
