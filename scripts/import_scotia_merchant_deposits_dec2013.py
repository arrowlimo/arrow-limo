#!/usr/bin/env python3
"""
Import ONLY the missing Merchant Deposit Credits from Scotia Bank December 2013.
These are credit card batch deposits that were missing from QuickBooks reconciliation.
"""

import os
import sys
import psycopg2
import hashlib

ACCOUNT = '903990106011'
DRY_RUN = '--write' not in sys.argv

# Merchant Deposit Credits extracted from bank statement screenshots Dec 2-29 ONLY
# These are DEPOSITS (credits) - money coming IN from credit card processing
# EXCLUDING Dec 30-31 which are already in QuickBooks data as aggregate "Deposit" entries
MERCHANT_DEPOSITS_DEC_2013 = [
    # December 2
    ('2013-12-02', 'Merchant Deposit Credit 566756800000 00001 VISA', None, 418.86),
    ('2013-12-02', 'Merchant Deposit Credit 566756800000 00001 MCARD', None, 1950.90),
    ('2013-12-02', 'Merchant Deposit Credit 566756800000 00001 VISA', None, 616.46),
    ('2013-12-02', 'Merchant Deposit Credit 566756800000 00001 VISA', None, 939.66),
    ('2013-12-02', 'Merchant Deposit Credit 566756800000 00001 VISA', None, 234.85),
    
    # December 3
    ('2013-12-03', 'Merchant Deposit Credit 566756800000 00001 MCARD', None, 2079.24),
    ('2013-12-03', 'Merchant Deposit Credit 566756800000 00001 VISA', None, 935.80),
    
    # December 4
    ('2013-12-04', 'Merchant Deposit Credit 566756800000 00001 VISA', None, 1103.12),
    ('2013-12-04', 'Merchant Deposit Credit 566756800000 00001 MCARD', None, 187.88),
    
    # December 6
    ('2013-12-06', 'Merchant Deposit Credit 566756800000 00001 MCARD', None, 250.37),
    ('2013-12-06', 'Merchant Deposit Credit 566756800000 00001 VISA', None, 41.85),
    
    # December 9
    ('2013-12-09', 'Merchant Deposit Credit 566756800000 00001 VISA', None, 843.50),
    ('2013-12-09', 'Merchant Deposit Credit 566756800000 00001 VISA', None, 1855.17),
    ('2013-12-09', 'Merchant Deposit Credit 566756800000 00001 MCARD', None, 535.89),
    ('2013-12-09', 'Merchant Deposit Credit 566756800000 00001 MCARD', None, 205.00),
    ('2013-12-09', 'Merchant Deposit Credit 566756800000 00001 VISA', None, 1283.03),
    
    # December 10
    ('2013-12-10', 'Merchant Deposit Credit 566756800000 00001 DEBITCD D', None, 26.25),
    ('2013-12-10', 'Merchant Deposit Credit 566756800000 00001 VISA', None, 4356.97),
    ('2013-12-10', 'Merchant Deposit Credit 566756800000 00001 MCARD', None, 82.69),
    
    # December 11
    ('2013-12-11', 'Merchant Deposit Credit 566756800000 00001 VISA', None, 1013.08),
    
    # December 12
    ('2013-12-12', 'Merchant Deposit Credit 566756800000 00001 VISA', None, 846.53),
    
    # December 13
    ('2013-12-13', 'Merchant Deposit Credit 566756800000 00001 VISA', None, 156.93),
    
    # December 16
    ('2013-12-16', 'Merchant Deposit Credit 566756800000 00001 VISA', None, 2618.69),
    ('2013-12-16', 'Merchant Deposit Credit 566756800000 00001 MCARD', None, 1835.00),
    ('2013-12-16', 'Merchant Deposit Credit 566756800000 00001 DEBITCD D', None, 99.23),
    ('2013-12-16', 'Merchant Deposit Credit 566756800000 00001 MCARD', None, 360.56),
    ('2013-12-16', 'Merchant Deposit Credit 566756800000 00001 VISA', None, 811.13),
    ('2013-12-16', 'Merchant Deposit Credit 566756800000 00001 VISA', None, 3776.37),
    
    # December 17
    ('2013-12-17', 'Merchant Deposit Credit 566756800000 00001 MCARD', None, 2681.00),
    ('2013-12-17', 'Merchant Deposit Credit 566756800000 00001 VISA', None, 206.94),
    
    # December 18
    ('2013-12-18', 'Merchant Deposit Credit 566756800000 00001 VISA', None, 1168.00),
    ('2013-12-18', 'Merchant Deposit Credit 566756800000 00001 MCARD', None, 336.25),
    
    # December 19
    ('2013-12-19', 'Merchant Deposit Credit 566756800000 00001 VISA', None, 2617.50),
    
    # December 20
    ('2013-12-20', 'Merchant Deposit Credit 566756800000 00001 VISA', None, 425.00),
    ('2013-12-20', 'Merchant Deposit Credit 566756800000 00001 MCARD', None, 175.00),
    
    # December 23
    ('2013-12-23', 'Merchant Deposit Credit 566756800000 00001 VISA', None, 2654.01),
    ('2013-12-23', 'Merchant Deposit Credit 566756800000 00001 VISA', None, 2691.04),
    ('2013-12-23', 'Merchant Deposit Credit 566756800000 00001 MCARD', None, 255.58),
    ('2013-12-23', 'Merchant Deposit Credit 566756800000 00001 VISA', None, 2105.07),
    
    # December 24
    ('2013-12-24', 'Merchant Deposit Credit 566756800000 00001 VISA', None, 4333.94),
    
    # December 27
    ('2013-12-27', 'Merchant Deposit Credit 566756800000 00001 MCARD', None, 206.00),
    
    # Dec 30-31 already in database as "Deposit" entries - DO NOT ADD
]

def get_conn():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REDACTED***')
    )

def generate_hash(date_str, description, amount):
    """Generate deterministic hash for transaction."""
    hash_input = f"{date_str}|{description}|{amount}".encode('utf-8')
    return hashlib.sha256(hash_input).hexdigest()

def main():
    print("\n" + "="*80)
    print("IMPORT MISSING MERCHANT DEPOSIT CREDITS - SCOTIA DECEMBER 2013")
    print("="*80)
    print(f"Account: {ACCOUNT}")
    print(f"Mode: {'DRY RUN' if DRY_RUN else 'WRITE'}")
    print(f"Merchant deposits to add: {len(MERCHANT_DEPOSITS_DEC_2013)}")
    
    conn = get_conn()
    cur = conn.cursor()
    
    # Check existing data
    cur.execute("""
        SELECT COUNT(*), SUM(credit_amount)
        FROM banking_transactions
        WHERE account_number = %s 
        AND transaction_date >= '2013-12-01' 
        AND transaction_date <= '2013-12-31'
    """, (ACCOUNT,))
    existing_count, existing_credits = cur.fetchone()
    
    print(f"\nBefore import:")
    print(f"  Total Dec 2013 transactions: {existing_count}")
    print(f"  Total credits: ${float(existing_credits or 0):,.2f}")
    
    # Load existing hashes
    cur.execute("""
        SELECT source_hash FROM banking_transactions
        WHERE account_number = %s
        AND source_hash IS NOT NULL
    """, (ACCOUNT,))
    existing_hashes = {row[0] for row in cur.fetchall()}
    
    # Prepare transactions
    to_import = []
    skipped = []
    
    for txn_date, description, debit, credit in MERCHANT_DEPOSITS_DEC_2013:
        source_hash = generate_hash(txn_date, description, credit)
        
        if source_hash in existing_hashes:
            skipped.append((txn_date, description, credit))
        else:
            to_import.append((txn_date, description, debit, credit, source_hash))
    
    print(f"\nTo import: {len(to_import)} NEW merchant deposits")
    print(f"Skipped (already in DB): {len(skipped)}")
    
    if len(to_import) == 0:
        print("\n[OK] No new merchant deposits to import")
        cur.close()
        conn.close()
        return
    
    # Calculate totals
    total_credits = sum(t[3] for t in to_import if t[3])
    
    print(f"\nNew deposit credits to add: ${total_credits:,.2f}")
    print(f"Expected total after import: ${float(existing_credits or 0) + total_credits:,.2f}")
    print(f"Statement shows: $70,463.81 total deposits")
    
    if DRY_RUN:
        print("\n[DRY RUN] No changes applied.")
        print("Run with --write to import.")
        cur.close()
        conn.close()
        return
    
    # Import transactions
    print("\n" + "="*80)
    print("IMPORTING MERCHANT DEPOSITS...")
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
    print(f"\n[SUCCESS] Imported {imported} merchant deposit transactions")
    
    # Final verification
    cur.execute("""
        SELECT 
            COUNT(*), 
            SUM(debit_amount), 
            SUM(credit_amount)
        FROM banking_transactions
        WHERE account_number = %s 
        AND transaction_date >= '2013-12-01'
        AND transaction_date <= '2013-12-31'
    """, (ACCOUNT,))
    final_count, final_debits, final_credits = cur.fetchone()
    
    print(f"\n{'='*80}")
    print(f"UPDATED DECEMBER 2013 TOTALS")
    print(f"{'='*80}")
    print(f"Total transactions: {final_count}")
    print(f"Total debits: ${float(final_debits or 0):,.2f}")
    print(f"Total credits: ${float(final_credits or 0):,.2f}")
    print(f"Net change: ${float(final_credits or 0) - float(final_debits or 0):+,.2f}")
    
    print(f"\nComparison to statement:")
    print(f"  Statement: $59,578.37 debits, $70,463.81 credits")
    debit_diff = abs(float(final_debits or 0) - 59578.37)
    credit_diff = abs(float(final_credits or 0) - 70463.81)
    print(f"  Variance: ${debit_diff:.2f} debits, ${credit_diff:.2f} credits")
    
    if credit_diff < 100:
        print("\n✅ Excellent - credits now match within $100!")
    
    cur.close()
    conn.close()
    
    print("\n" + "="*80)

if __name__ == '__main__':
    main()
