#!/usr/bin/env python3
"""
Import May, June, and July 2013 CIBC banking data - batch processing.
May: -$899.63 → -$1,650.48
June: -$1,650.48 → -$2,185.88  
July: -$2,185.88 → -$2,731.91
"""

import os
import sys
import psycopg2
import hashlib

ACCOUNT = '0228362'
DRY_RUN = '--write' not in sys.argv

# May 2013 transactions (from earlier PDF)
MAY_2013 = [
    ('2013-05-01', 'DEBIT MEMO MERCH#4017775 GBL MERCH FEES', 131.23, None),
    ('2013-05-01', 'RENT/LEASE 000000000000000 LEASE FINANCE GR', 809.08, None),
    ('2013-05-01', 'INSURANCE Cooperators CSI', 104.03, None),
    ('2013-05-01', 'CORRECTION 00339', None, 104.03),
    ('2013-05-01', 'CORRECTION 00339', None, 131.23),
    ('2013-05-01', 'CORRECTION 00339', None, 809.08),
    ('2013-05-01', 'NSF CHARGE 00339', 135.00, None),
    ('2013-05-06', 'DEBIT MEMO REPRESENTED DR GBL MERCH FEES', 131.23, None),
    ('2013-05-06', 'RENT/LEASE 000000000000000 LEASE FINANCE GR', 101.14, None),
    ('2013-05-06', 'CORRECTION 00339', None, 101.14),
    ('2013-05-06', 'CORRECTION 00339', None, 131.23),
    ('2013-05-06', 'NSF CHARGE 00339', 90.00, None),
    ('2013-05-08', 'RENT/LEASE 000000000000000 LEASE FINANCE GR', 404.56, None),
    ('2013-05-08', 'RENT/LEASE 000000000000000 LEASE FINANCE GR', 202.27, None),
    ('2013-05-08', 'CORRECTION 00339', None, 202.27),
    ('2013-05-08', 'CORRECTION 00339', None, 404.56),
    ('2013-05-08', 'NSF CHARGE 00339', 90.00, None),
    ('2013-05-13', 'RENT/LEASE 000000000000000 LEASE FINANCE GR', 101.14, None),
    ('2013-05-13', 'CORRECTION 00339', None, 101.14),
    ('2013-05-13', 'NSF CHARGE 00339', 45.00, None),
    ('2013-05-14', 'RENT/LEASE 000000000000000 LEASE FINANCE GR', 809.08, None),
    ('2013-05-14', 'CORRECTION 00339', None, 809.08),
    ('2013-05-14', 'NSF CHARGE 00339', 45.00, None),
    ('2013-05-15', 'RENT/LEASE 000000000000000 LEASE FINANCE GR', 202.27, None),
    ('2013-05-15', 'CORRECTION 00339', None, 202.27),
    ('2013-05-15', 'NSF CHARGE 00339', 45.00, None),
    ('2013-05-24', 'INSURANCE IFS PREMIUM FIN', 2383.24, None),
    ('2013-05-24', 'INSURANCE Cooperators CSI', 50.00, None),
    ('2013-05-24', 'CORRECTION 00339', None, 50.00),
    ('2013-05-24', 'CORRECTION 00339', None, 2383.24),
    ('2013-05-24', 'NSF CHARGE 00339', 90.00, None),
    ('2013-05-31', 'RENT/LEASE 000000000000000 LEASE FINANCE GR', 1011.35, None),
    ('2013-05-31', 'RENT/LEASE 000000000000000 LEASE FINANCE GR', 505.70, None),
    ('2013-05-31', 'INSURANCE Cooperators CSI', 50.00, None),
    ('2013-05-31', 'CORRECTION 00339', None, 50.00),
    ('2013-05-31', 'CORRECTION 00339', None, 505.70),
    ('2013-05-31', 'CORRECTION 00339', None, 1011.35),
    ('2013-05-31', 'NSF CHARGE 00339', 135.00, None),
    ('2013-05-31', 'ACCOUNT FEE', 50.00, None),
    ('2013-05-31', 'OVERDRAFT INTEREST', 22.85, None),
    ('2013-05-31', 'PAPER STMT/MT FEE', 3.00, None),
]

# June 2013 transactions
JUNE_2013 = [
    ('2013-06-03', 'DEBIT MEMO MERCH#4017775 GBL MERCH FEES', 91.23, None),
    ('2013-06-03', 'CORRECTION 00339', None, 91.23),
    ('2013-06-03', 'NSF CHARGE 00339', 45.00, None),
    ('2013-06-06', 'DEBIT MEMO REPRESENTED DR GBL MERCH FEES', 91.23, None),
    ('2013-06-06', 'RENT/LEASE 000000000000000 LEASE FINANCE GR', 101.14, None),
    ('2013-06-06', 'CORRECTION 00339', None, 91.23),
    ('2013-06-06', 'CORRECTION 00339', None, 101.14),
    ('2013-06-06', 'NSF CHARGE 00339', 45.00, None),
    ('2013-06-10', 'RENT/LEASE 000000000000000 LEASE FINANCE GR', 202.27, None),
    ('2013-06-10', 'RENT/LEASE 000000000000000 LEASE FINANCE GR', 1011.35, None),
]

# July 2013 transactions
JULY_2013 = [
    ('2013-07-02', 'DEBIT MEMO MERCH#4017775 GBL MERCH FEES', 91.23, None),
    ('2013-07-02', 'INSURANCE Cooperators CSI', 100.00, None),
    ('2013-07-02', 'CORRECTION 00339', None, 91.23),
    ('2013-07-02', 'CORRECTION 00339', None, 100.00),
    ('2013-07-02', 'NSF CHARGE 00339', 90.00, None),
    ('2013-07-05', 'DEBIT MEMO REPRESENTED DR GBL MERCH FEES', 91.23, None),
    ('2013-07-05', 'CORRECTION 00339', None, 91.23),
    ('2013-07-08', 'RENT/LEASE 000000000000000 LEASE FINANCE GR', 202.27, None),
    ('2013-07-08', 'RENT/LEASE 000000000000000 LEASE FINANCE GR', 101.14, None),
    ('2013-07-08', 'CORRECTION 00339', None, 101.14),
    ('2013-07-08', 'CORRECTION 00339', None, 202.27),
    ('2013-07-08', 'NSF CHARGE 00339', 90.00, None),
    ('2013-07-16', 'RENT/LEASE 000000000000000 LEASE FINANCE GR', 1415.89, None),
    ('2013-07-16', 'RENT/LEASE 000000000000000 LEASE FINANCE GR', 707.98, None),
    ('2013-07-16', 'CORRECTION 00339', None, 707.98),
    ('2013-07-16', 'CORRECTION 00339', None, 1415.89),
    ('2013-07-16', 'NSF CHARGE 00339', 90.00, None),
    ('2013-07-24', 'RENT/LEASE 000000000000000 LEASE FINANCE GR', 1415.89, None),
    ('2013-07-24', 'RENT/LEASE 000000000000000 LEASE FINANCE GR', 707.98, None),
    ('2013-07-24', 'CORRECTION 00339', None, 707.98),
    ('2013-07-24', 'CORRECTION 00339', None, 1415.89),
    ('2013-07-24', 'NSF CHARGE 00339', 90.00, None),
    ('2013-07-31', 'RENT/LEASE 000000000000000 LEASE FINANCE GR', 1415.89, None),
    ('2013-07-31', 'RENT/LEASE 000000000000000 LEASE FINANCE GR', 707.98, None),
    ('2013-07-31', 'CORRECTION 00339', None, 707.98),
    ('2013-07-31', 'CORRECTION 00339', None, 1415.89),
    ('2013-07-31', 'NSF CHARGE 00339', 90.00, None),
    ('2013-07-31', 'ACCOUNT FEE', 50.00, None),
    ('2013-07-31', 'OVERDRAFT INTEREST', 43.03, None),
    ('2013-07-31', 'PAPER STMT/MT FEE', 3.00, None),
]

ALL_TRANSACTIONS = MAY_2013 + JUNE_2013 + JULY_2013

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
    print("IMPORT MAY, JUNE, JULY 2013 CIBC BANKING DATA - BATCH")
    print("="*80)
    print(f"Account: {ACCOUNT}")
    print(f"Mode: {'DRY RUN' if DRY_RUN else 'WRITE'}")
    print(f"May transactions: {len(MAY_2013)}")
    print(f"June transactions: {len(JUNE_2013)}")
    print(f"July transactions: {len(JULY_2013)}")
    print(f"Total transactions: {len(ALL_TRANSACTIONS)}")
    
    conn = get_conn()
    cur = conn.cursor()
    
    # Check existing data
    cur.execute("""
        SELECT COUNT(*) FROM banking_transactions
        WHERE account_number = %s 
        AND transaction_date >= '2013-05-01' 
        AND transaction_date <= '2013-07-31'
    """, (ACCOUNT,))
    existing_count = cur.fetchone()[0]
    
    print(f"\nExisting May-Jul 2013 transactions in DB: {existing_count}")
    
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
    for month in ['05', '06', '07']:
        cur.execute("""
            SELECT COUNT(*), SUM(debit_amount), SUM(credit_amount)
            FROM banking_transactions
            WHERE account_number = %s 
            AND EXTRACT(YEAR FROM transaction_date) = 2013
            AND EXTRACT(MONTH FROM transaction_date) = %s
        """, (ACCOUNT, int(month)))
        count, debits, credits = cur.fetchone()
        month_name = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul'][int(month)]
        print(f"{month_name} 2013: {count} txns, ${float(debits or 0):,.2f} debits, ${float(credits or 0):,.2f} credits")
    
    cur.close()
    conn.close()
    
    print("\n" + "="*80)

if __name__ == '__main__':
    main()
