#!/usr/bin/env python3
"""
Import January 2013 CIBC banking data from reconciliation report.

Based on the PDF screenshots:
- Opening balance Jan 01: $21.21
- Closing balance Jan 31: -$244.65
- Transaction detail pages show line-by-line entries
- Summary page shows cleared vs new transactions
"""

import os
import sys
import psycopg2
from datetime import date
import hashlib

ACCOUNT = '0228362'
DRY_RUN = '--write' not in sys.argv

# Transaction data from Jan 2013 reconciliation report
# Format: (date, description, debit, credit)
TRANSACTIONS = [
    # Jan 01 - Opening balance (not a transaction, just starting point)
    
    # Jan 02
    ('2013-01-02', 'DEBIT MEMO MERCH#4017775 GBL MERCH FEES', 316.88, None),
    ('2013-01-02', 'CORRECTION 00339', None, 316.88),
    ('2013-01-02', 'NSF CHARGE 00339', 45.00, None),
    
    # Jan 07
    ('2013-01-07', 'M M BEBRESENTED DR GBL MERCH FEES', 316.88, None),
    ('2013-01-07', 'RENT/LEASE 000000000000000 LEASE FINANCE GR', 101.14, None),
    ('2013-01-07', 'CORRECTION 00339', None, 101.14),
    
    # Jan 08
    ('2013-01-08', 'RENT/LEASE 000000000000000 LEASE FINANCE GR', 202.27, None),
    ('2013-01-08', 'CORRECTION 00339', None, 202.27),
    ('2013-01-08', 'NSF CHARGE 00339', 45.00, None),
    
    # Jan 14
    ('2013-01-14', 'RENT/LEASE 000000000000000 LEASE FINANCE GR', 101.14, None),
    ('2013-01-14', 'CORRECTION 00339', None, 101.14),
    ('2013-01-14', 'NSF CHARGE 00339', 45.00, None),
    
    # Jan 15
    ('2013-01-15', 'CREDIT MEMO GBL MERCH#4017775', None, 96.26),
    
    # Jan 15 (continued)
    ('2013-01-15', 'RENT/LEASE 000000000000000 LEASE FINANCE GR', 404.54, None),
    ('2013-01-15', 'CORRECTION 00339', None, 404.54),
    ('2013-01-15', 'NSF CHARGE 00339', 45.00, None),
    
    # Jan 21
    ('2013-01-21', 'RENT/LEASE 000000000000000 LEASE FINANCE GR', 101.14, None),
    ('2013-01-21', 'CORRECTION 00339', None, 101.14),
    ('2013-01-21', 'NSF CHARGE 00339', 45.00, None),
    
    # Jan 22
    ('2013-01-22', 'CREDIT MEMO GBL PMC', None, 170.00),
    
    # Jan 24
    ('2013-01-24', 'INSURANCE #5 PREMIUM FIN INSURANCE Coaperation CSI', 2383.24, None),
    ('2013-01-24', 'CORRECTION 00339', None, 105.15),
    ('2013-01-24', 'CORRECTION 00339', None, 2383.24),
    ('2013-01-24', 'NSF CHARGE 00339', 90.00, None),
    
    # Jan 28
    ('2013-01-28', 'RENT/LEASE 000000000000000 LEASE FINANCE GR', 404.54, None),
    ('2013-01-28', 'CORRECTION 00339', None, 404.54),
    ('2013-01-28', 'NSF CHARGE 00339', 45.00, None),
    
    # Jan 31
    ('2013-01-31', 'INSURANCE Coaperation CSI', None, 105.15),
    ('2013-01-31', 'CORRECTION 00339', None, 105.15),
    ('2013-01-31', 'NSF CHARGE 00339', 45.00, None),
    ('2013-01-31', 'ACCOUNT FEE', 35.00, None),
    ('2013-01-31', 'OVERDRAFT INTEREST', 2.12, None),
]

def get_conn():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***')
    )

def generate_hash(date_str, description, debit, credit):
    """Generate deterministic hash for transaction."""
    hash_input = f"{date_str}|{description}|{debit or 0}|{credit or 0}".encode('utf-8')
    return hashlib.sha256(hash_input).hexdigest()

def main():
    print("\n" + "="*80)
    print("IMPORT JANUARY 2013 CIBC BANKING DATA")
    print("="*80)
    print(f"Account: {ACCOUNT}")
    print(f"Mode: {'DRY RUN' if DRY_RUN else 'WRITE'}")
    print(f"Transactions to import: {len(TRANSACTIONS)}")
    
    conn = get_conn()
    cur = conn.cursor()
    
    # Check existing data
    cur.execute("""
        SELECT COUNT(*) FROM banking_transactions
        WHERE account_number = %s 
        AND transaction_date >= '2013-01-01' 
        AND transaction_date <= '2013-01-31'
    """, (ACCOUNT,))
    existing_count = cur.fetchone()[0]
    
    print(f"\nExisting Jan 2013 transactions in DB: {existing_count}")
    
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
    
    for txn_date, description, debit, credit in TRANSACTIONS:
        source_hash = generate_hash(txn_date, description, debit, credit)
        
        if source_hash in existing_hashes:
            skipped.append((txn_date, description, debit, credit))
        else:
            to_import.append((txn_date, description, debit, credit, source_hash))
    
    print(f"\nTo import: {len(to_import)} transactions")
    print(f"Skipped (duplicates): {len(skipped)}")
    
    if len(to_import) == 0:
        print("\n[OK] No new transactions to import")
        return
    
    # Show sample
    print("\nSample transactions to import (first 10):")
    print("-"*80)
    for i, (txn_date, desc, debit, credit, _) in enumerate(to_import[:10], 1):
        amount = f"${debit:.2f} W" if debit else f"${credit:.2f} D"
        print(f"{i:2d}. {txn_date} | {amount:>12} | {desc[:50]}")
    
    if len(to_import) > 10:
        print(f"... and {len(to_import)-10} more")
    
    # Calculate totals
    total_debits = sum(t[2] for t in to_import if t[2])
    total_credits = sum(t[3] for t in to_import if t[3])
    
    print(f"\nTotal debits: ${total_debits:,.2f}")
    print(f"Total credits: ${total_credits:,.2f}")
    print(f"Net change: ${total_credits - total_debits:+,.2f}")
    
    if DRY_RUN:
        print("\n[DRY RUN] No changes applied to database.")
        print("Run with --write flag to apply changes.")
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
    
    # Verify
    cur.execute("""
        SELECT COUNT(*), SUM(debit_amount), SUM(credit_amount)
        FROM banking_transactions
        WHERE account_number = %s 
        AND transaction_date >= '2013-01-01' 
        AND transaction_date <= '2013-01-31'
    """, (ACCOUNT,))
    count, debits, credits = cur.fetchone()
    
    print("\n" + "="*80)
    print("VERIFICATION")
    print("="*80)
    print(f"Total Jan 2013 transactions in DB: {count}")
    print(f"Total debits: ${float(debits or 0):,.2f}")
    print(f"Total credits: ${float(credits or 0):,.2f}")
    
    cur.close()
    conn.close()
    
    print("\n" + "="*80)

if __name__ == '__main__':
    main()
