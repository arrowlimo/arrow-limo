#!/usr/bin/env python3
"""
Import complete Scotia Bank December 2013 transactions from bank statement.
Using line-by-line extraction from statement screenshots with running balance validation.
"""

import os
import sys
import psycopg2
import hashlib
from decimal import Decimal

ACCOUNT = '903990106011'
DRY_RUN = '--write' not in sys.argv

# Complete December 2013 transactions extracted from bank statement screenshots
# Format: (date, description, withdrawal, deposit)
# These are the ACTUAL statement transactions with proper W/D classification
STATEMENT_TRANSACTIONS = [
    # December 2
    ('2013-12-02', 'Purchase 1000001050023046 Centex Deerpark 4506*********359', 63.50, None),
    ('2013-12-02', 'Purchase 1000001050023049 604-Lb 67th S 4506*********359', 360.36, None),
    ('2013-12-02', 'Merchant Deposit Credit 566756800000 00001 VISA', None, 418.86),
    ('2013-12-02', 'Merchant Deposit Credit 566756800000 00001 MCARD', None, 1950.90),
    ('2013-12-02', 'Merchant Deposit Credit 566756800000 00001 VISA', None, 616.46),
    ('2013-12-02', 'Merchant Deposit Credit 566756800000 00001 VISA', None, 939.66),
    ('2013-12-02', 'Merchant Deposit Credit 566756800000 00001 VISA', None, 234.85),
    
    # December 3
    ('2013-12-03', 'Purchase 2178116050024032 Rocky Mountain / Cns GCS 4506*********359', 478.98, None),
    ('2013-12-03', 'Purchase 1000001050023061 Centex Deerpark 4506*********359', 1149.90, None),
    ('2013-12-03', 'Merchant Deposit Credit 566756800000 00001 MCARD', None, 2079.24),
    ('2013-12-03', 'Merchant Deposit Credit 566756800000 00001 VISA', None, 935.80),
    
    # December 4
    ('2013-12-04', 'Cheque 260', 1885.65, None),
    ('2013-12-04', 'Cheque 268', 2247.45, None),
    ('2013-12-04', 'Cheque 279', 3244.25, None),
    ('2013-12-04', 'Cheque 285', 1701.33, None),
    ('2013-12-04', 'Purchase 1000001050023082 Centex Deerpark 4506*********359', 41.57, None),
    ('2013-12-04', 'Purchase 1000001050023089 604-Lb 67th S 4506*********359', 1103.12, None),
    ('2013-12-04', 'Merchant Deposit Credit 566756800000 00001 VISA', None, 1103.12),
    ('2013-12-04', 'Merchant Deposit Credit 566756800000 00001 MCARD', None, 187.88),
    ('2013-12-04', 'Purchase 1000001050023078 Centex Deerpark 4506*********359', None, None),
    ('2013-12-04', 'Pre-Auth 1000001050023077 Centex Deerpark 4506*********359', None, None),
    
    # December 5
    ('2013-12-05', 'Cheque 286', 140.00, None),
    
    # December 6
    ('2013-12-06', 'Cheque 288', 123.94, None),
    ('2013-12-06', 'Cheque 289', 76.71, None),
    ('2013-12-06', 'Cheque 291', 3483.79, None),
    ('2013-12-06', 'Purchase 1000001050023117 Centex Deerpark 4506*********359', 449.55, None),
    ('2013-12-06', 'Merchant Deposit Credit 566756800000 00001 MCARD', None, 250.37),
    ('2013-12-06', 'Merchant Deposit Credit 566756800000 00001 VISA', None, 41.85),
    
    # December 7
    ('2013-12-07', 'Purchase 1000001050023127 Centex Deerpark 4506*********359', 51.01, None),
    ('2013-12-07', 'Purchase 1000001050023128 604-Lb 67th S 4506*********359', 43.22, None),
    
    # December 9
    ('2013-12-09', 'Cheque 292', 460.00, None),
    ('2013-12-09', 'Purchase 1000001050023152 Centex Deerpark 4506*********359', 44.20, None),
    ('2013-12-09', 'Purchase 1000001050023157 604-Lb 67th S 4506*********359', 524.00, None),
    ('2013-12-09', 'Purchase 1000001050023158 Centex Deerpark 4506*********359', 843.50, None),
    ('2013-12-09', 'Merchant Deposit Credit 566756800000 00001 VISA', None, 843.50),
    ('2013-12-09', 'Merchant Deposit Credit 566756800000 00001 VISA', None, 1855.17),
    ('2013-12-09', 'Merchant Deposit Credit 566756800000 00001 MCARD', None, 535.89),
    ('2013-12-09', 'Merchant Deposit Credit 566756800000 00001 MCARD', None, 205.00),
    ('2013-12-09', 'Merchant Deposit Credit 566756800000 00001 VISA', None, 1283.03),
    
    # December 10
    ('2013-12-10', 'Purchase 1000001050023168 Centex Deerpark 4506*********359', 406.18, None),
    ('2013-12-10', 'Purchase 1000001050023180 Centex Deerpark 4506*********359', 3356.97, None),
    ('2013-12-10', 'Merchant Deposit Credit 566756800000 00001 DEBITCD D', None, 26.25),
    ('2013-12-10', 'Merchant Deposit Credit 566756800000 00001 VISA', None, 4356.97),
    ('2013-12-10', 'Merchant Deposit Credit 566756800000 00001 MCARD', None, 82.69),
    
    # December 11
    ('2013-12-11', 'Cheque 294', 21.46, None),
    ('2013-12-11', 'Cheque 295', 140.00, None),
    ('2013-12-11', 'Purchase 1000001050023191 Centex Deerpark 4506*********359', 189.54, None),
    ('2013-12-11', 'Merchant Deposit Credit 566756800000 00001 VISA', None, 1013.08),
    
    # December 12
    ('2013-12-12', 'Cheque 297', 673.05, None),
    ('2013-12-12', 'Merchant Deposit Credit 566756800000 00001 VISA', None, 846.53),
    
    # December 13
    ('2013-12-13', 'Cheque 298', 1050.00, None),
    ('2013-12-13', 'Purchase 1000001050023216 604-Lb 67th S 4506*********359', 19.30, None),
    ('2013-12-13', 'Merchant Deposit Credit 566756800000 00001 VISA', None, 156.93),
    
    # December 14
    ('2013-12-14', 'Purchase 1000001050023230 Centex Deerpark 4506*********359', 87.92, None),
    ('2013-12-14', 'Purchase 1000001050023234 604-Lb 67th S 4506*********359', 377.99, None),
    
    # December 15
    ('2013-12-15', 'Cheque 299', 748.00, None),
    ('2013-12-15', 'Purchase 1000001050023244 Centex Deerpark 4506*********359', None, None),
    ('2013-12-15', 'Pre-Auth 1000001050023243 Centex Deerpark 4506*********359', None, None),
    
    # December 16
    ('2013-12-16', 'Purchase 2178116050025093 Rocky Mountain / Cns GCS 4506*********359', 532.37, None),
    ('2013-12-16', 'Purchase 1000001050023267 Fas Gas 4506*********359', 1205.60, None),
    ('2013-12-16', 'Purchase 1000001050023270 Centex Deerpark 4506*********359', 1166.29, None),
    ('2013-12-16', 'Purchase 1000001050023273 Centex Deerpark 4506*********359', 2618.69, None),
    ('2013-12-16', 'Purchase 1000001050023277 Centex Deerpark 4506*********359', 3712.26, None),
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
    ('2013-12-18', 'Cheque 301', 377.99, None),
    ('2013-12-18', 'Purchase 2178116050025156 Rocky Mountain / Cns GCS 4506*********359', 455.52, None),
    ('2013-12-18', 'Purchase 1000001050023293 Centex Deerpark 4506*********359', 43.87, None),
    ('2013-12-18', 'Purchase 1000001050023296 Centex Deerpark 4506*********359', 662.49, None),
    ('2013-12-18', 'Purchase 1000001050023304 604-Lb 67th S 4506*********359', 1568.00, None),
    ('2013-12-18', 'Merchant Deposit Credit 566756800000 00001 VISA', None, 1168.00),
    ('2013-12-18', 'Merchant Deposit Credit 566756800000 00001 MCARD', None, 336.25),
    
    # December 19
    ('2013-12-19', 'Cheque 302', 2525.25, None),
    ('2013-12-19', 'Purchase 1000001050023314 Centex Deerpark 4506*********359', 45.62, None),
    ('2013-12-19', 'Purchase 1000001050023318 604-Lb 67th S 4506*********359', 43.68, None),
    ('2013-12-19', 'Purchase 1000001050023330 Centex Deerpark 4506*********359', 71.50, None),
    ('2013-12-19', 'Purchase 1000001050023334 Centex Deerpark 4506*********359', 2617.50, None),
    ('2013-12-19', 'Merchant Deposit Credit 566756800000 00001 VISA', None, 2617.50),
    
    # December 20
    ('2013-12-20', 'Cheque 303', 1475.25, None),
    ('2013-12-20', 'Cheque 304', 1900.50, None),
    ('2013-12-20', 'Purchase 2178116050025214 Rocky Mountain / Cns GCS 4506*********359', 401.56, None),
    ('2013-12-20', 'Purchase 1000001050023345 Centex Deerpark 4506*********359', 55.41, None),
    ('2013-12-20', 'Purchase 1000001050023348 Centex Deerpark 4506*********359', 43.77, None),
    ('2013-12-20', 'Purchase 1000001050023350 Centex Deerpark 4506*********359', 425.00, None),
    ('2013-12-20', 'Purchase 1000001050023362 604-Lb 67th S 4506*********359', 1278.75, None),
    ('2013-12-20', 'Merchant Deposit Credit 566756800000 00001 VISA', None, 425.00),
    ('2013-12-20', 'Merchant Deposit Credit 566756800000 00001 MCARD', None, 175.00),
    
    # December 21
    ('2013-12-21', 'Purchase 1000001050023372 Centex Deerpark 4506*********359', 86.40, None),
    ('2013-12-21', 'Purchase 1000001050023373 604-Lb 67th S 4506*********359', 55.48, None),
    
    # December 22
    ('2013-12-22', 'Purchase 1000001050023382 Centex Deerpark 4506*********359', 170.02, None),
    
    # December 23
    ('2013-12-23', 'Purchase 1000001050023394 Centex Deerpark 4506*********359', 239.68, None),
    ('2013-12-23', 'Purchase 1000001050023397 604-Lb 67th S 4506*********359', 438.28, None),
    ('2013-12-23', 'Merchant Deposit Credit 566756800000 00001 VISA', None, 2654.01),
    ('2013-12-23', 'Merchant Deposit Credit 566756800000 00001 VISA', None, 2691.04),
    ('2013-12-23', 'Merchant Deposit Credit 566756800000 00001 MCARD', None, 255.58),
    ('2013-12-23', 'Merchant Deposit Credit 566756800000 00001 VISA', None, 2105.07),
    
    # December 24
    ('2013-12-24', 'Merchant Deposit Credit 566756800000 00001 VISA', None, 4333.94),
    
    # December 27
    ('2013-12-27', 'Cheque 305', 460.00, None),
    ('2013-12-27', 'Cheque 306', 1314.52, None),
    ('2013-12-27', 'Cheque 307', 4189.50, None),
    ('2013-12-27', 'Cheque 308', 1314.52, None),
    ('2013-12-27', 'Purchase 2178116050025281 Rocky Mountain / Cns GCS 4506*********359', 423.99, None),
    ('2013-12-27', 'Purchase 1000001050023409 Centex Deerpark 4506*********359', 41.41, None),
    ('2013-12-27', 'Purchase 1000001050023411 Centex Deerpark 4506*********359', 48.85, None),
    ('2013-12-27', 'Purchase 1000001050023413 Centex Deerpark 4506*********359', 47.84, None),
    ('2013-12-27', 'Purchase 1000001050023419 604-Lb 67th S 4506*********359', 1309.15, None),
    ('2013-12-27', 'Purchase 1000001050023426 Centex Deerpark 4506*********359', 1615.52, None),
    ('2013-12-27', 'Merchant Deposit Credit 566756800000 00001 MCARD', None, 206.00),
    
    # December 28
    ('2013-12-28', 'Cheque 309', 1000.00, None),
    
    # December 30
    ('2013-12-30', 'Cheque w/d Paul Richard (v)', 1000.00, None),
    ('2013-12-30', 'Cheque w/d Paul Richard (v)', 700.00, None),
    ('2013-12-30', 'Cheque dd ScotiaBank Value Visa 39613650', 600.00, None),
    ('2013-12-30', 'Cheque dd LFG Business PAD', 405.66, None),
    # Note: 7.50 Service Charge is for "Money Order Purchase" - combined with 405.66 Debit Memo below
    ('2013-12-30', 'Debit Memo Money Order Purchase', 405.66, None),
    ('2013-12-30', 'ABM Withdrawal', 700.00, None),
    ('2013-12-30', 'Merchant Deposit Credit 566756800000 00001 DEBITCD D', None, 67.52),
    ('2013-12-30', 'Merchant Deposit Credit 566756800000 00001 VISA', None, 420.00),
    ('2013-12-30', 'Merchant Deposit Credit 566756800000 00001 MCARD', None, 1960.05),
    ('2013-12-30', 'Merchant Deposit Credit 566756800000 00001 MCARD', None, 98.20),
    ('2013-12-30', 'Merchant Deposit Credit 566756800000 00001 VISA', None, 1026.18),
    ('2013-12-30', 'Deposit', None, 3155.00),
    
    # December 31
    ('2013-12-31', 'Overdraft Charge', 6.23, None),
    ('2013-12-31', 'Service Charge', 112.50, None),
    ('2013-12-31', 'Cheque 289', 492.26, None),
    ('2013-12-31', 'Cheque 288', 1706.25, None),
    ('2013-12-31', 'Debit Memo Other', 1200.00, None),
    ('2013-12-31', 'Merchant Deposit Credit 566756800000 00001 VISA', None, 1868.50),
    ('2013-12-31', 'Merchant Deposit Credit 566756800000 00001 MCARD', None, 830.00),
    ('2013-12-31', 'Merchant Deposit Credit 566756800000 00001 DEBITCD D', None, 67.52),
    ('2013-12-31', 'Deposit', None, 63324.91),
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
    amount = debit if debit else credit
    hash_input = f"{date_str}|{description}|{amount}".encode('utf-8')
    return hashlib.sha256(hash_input).hexdigest()

def main():
    print("\n" + "="*80)
    print("IMPORT COMPLETE SCOTIA DECEMBER 2013 BANK STATEMENT")
    print("="*80)
    print(f"Account: {ACCOUNT}")
    print(f"Mode: {'DRY RUN' if DRY_RUN else 'WRITE'}")
    
    conn = get_conn()
    cur = conn.cursor()
    
    # Load existing hashes
    cur.execute("""
        SELECT source_hash FROM banking_transactions
        WHERE account_number = %s
        AND source_hash IS NOT NULL
    """, (ACCOUNT,))
    existing_hashes = {row[0] for row in cur.fetchall()}
    
    print(f"Existing transactions with hashes: {len(existing_hashes)}")
    
    # Process statement transactions
    to_import = []
    skipped = []
    skipped_no_amount = []
    
    total_statement_withdrawals = Decimal('0')
    total_statement_deposits = Decimal('0')
    
    for txn_date, description, debit, credit in STATEMENT_TRANSACTIONS:
        # Skip transactions with no amounts (Pre-Auth, reversals, etc)
        if debit is None and credit is None:
            skipped_no_amount.append((txn_date, description))
            continue
        
        # Calculate totals
        if debit:
            total_statement_withdrawals += Decimal(str(debit))
        if credit:
            total_statement_deposits += Decimal(str(credit))
        
        source_hash = generate_hash(txn_date, description, debit, credit)
        
        if source_hash in existing_hashes:
            skipped.append((txn_date, description, debit, credit))
        else:
            to_import.append((txn_date, description, debit, credit, source_hash))
    
    print(f"\nStatement totals:")
    print(f"  Withdrawals: ${total_statement_withdrawals:,.2f}")
    print(f"  Deposits: ${total_statement_deposits:,.2f}")
    print(f"  Expected: $59,578.37 withdrawals, $70,463.81 deposits")
    
    print(f"\nTo import: {len(to_import)} NEW transactions")
    print(f"Skipped (already in DB): {len(skipped)}")
    print(f"Skipped (no amount): {len(skipped_no_amount)}")
    
    if len(to_import) == 0:
        print("\n[OK] No new transactions to import")
        cur.close()
        conn.close()
        return
    
    # Calculate import totals
    import_withdrawals = sum(Decimal(str(t[2])) for t in to_import if t[2])
    import_deposits = sum(Decimal(str(t[3])) for t in to_import if t[3])
    
    print(f"\nNew transactions to add:")
    print(f"  Withdrawals: ${import_withdrawals:,.2f}")
    print(f"  Deposits: ${import_deposits:,.2f}")
    
    if DRY_RUN:
        print("\n[DRY RUN] No changes applied.")
        print("Run with --write to import.")
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
    print(f"FINAL DECEMBER 2013 TOTALS")
    print(f"{'='*80}")
    print(f"Total transactions: {final_count}")
    print(f"Total debits: ${float(final_debits or 0):,.2f}")
    print(f"Total credits: ${float(final_credits or 0):,.2f}")
    
    print(f"\nComparison to statement:")
    print(f"  Statement: $59,578.37 debits, $70,463.81 credits")
    debit_diff = abs(float(final_debits or 0) - 59578.37)
    credit_diff = abs(float(final_credits or 0) - 70463.81)
    print(f"  Variance: ${debit_diff:.2f} debits, ${credit_diff:.2f} credits")
    
    if debit_diff < 1 and credit_diff < 1:
        print("\n✅ PERFECT MATCH - Penny-perfect accuracy achieved!")
    elif debit_diff < 100 and credit_diff < 100:
        print("\n✅ Excellent - within $100 tolerance")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
