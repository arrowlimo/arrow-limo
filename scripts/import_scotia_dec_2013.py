#!/usr/bin/env python3
"""
Import Scotia Bank December 2013 cleared transactions from QuickBooks reconciliation report.
Account: 903990106011
Beginning Balance: -$4,480.57
Ending Balance: $6,404.87
"""

import os
import sys
import psycopg2
import hashlib

ACCOUNT = '903990106011'
DRY_RUN = '--write' not in sys.argv

# December 2013 cleared transactions (93 cheques + 2 deposits)
# Format: (date, description, amount, is_deposit)
SCOTIA_DEC_2013 = [
    # Cheques and Payments (withdrawals)
    ('2013-11-01', 'Cheque 268 Jeff Bril', 36.79, False),
    ('2013-11-04', 'Cheque 266 Marc A Cole', 383.22, False),
    ('2013-11-29', 'Bill Pmt-Cheque 273 Community Networki...', 1359.75, False),
    ('2013-12-02', 'Cheque dd Chase Paymentech', 418.86, False),
    ('2013-12-02', 'Cheque dd Bank Charges & Int...', 5.00, False),
    ('2013-12-03', 'Cheque 274 Tammy Petitit', 1458.88, False),
    ('2013-12-03', 'Cheque dd Bank Charges & Int...', 170.00, False),
    ('2013-12-04', 'Cheque 280 Douglas Redmond', 1910.96, False),
    ('2013-12-04', 'Cheque 278 Stephen Meek', 1876.76, False),
    ('2013-12-04', 'Cheque 279 Jesse Gordon', 1762.90, False),
    ('2013-12-04', 'Cheque 282 Jeannie Shillington', 1210.95, False),
    ('2013-12-04', 'Cheque 275 Jonathan Korsh', 948.46, False),
    ('2013-12-04', 'Cheque 281 Paul Mansell', 941.09, False),
    ('2013-12-04', 'Cheque 277 Larry Taylor', 733.68, False),
    ('2013-12-04', 'Cheque 276 Jeff Bril', 632.84, False),
    ('2013-12-04', 'Cheque dd Esso', 140.03, False),
    ('2013-12-04', 'Cheque dd Fas Gas Plus', 65.70, False),
    ('2013-12-05', 'Cheque dd Money Mart', 140.00, False),
    ('2013-12-06', 'Cheque dd Berglund, Louise', 550.00, False),
    ('2013-12-06', 'Cheque w/d Paul Richard (v)', 400.00, False),
    ('2013-12-06', 'Cheque dd Fas Gas Plus', 142.00, False),
    ('2013-12-06', 'Cheque dd Princess Auto', 41.99, False),
    ('2013-12-07', 'Cheque dd Walmart', 49.23, False),
    ('2013-12-07', 'Cheque dd Fas Gas Plus', 45.00, False),
    ('2013-12-09', 'Cheque dd Heffner Lexus Toyota', 889.87, False),
    ('2013-12-09', 'Cheque dd Capital One MC', 650.00, False),
    ('2013-12-09', 'Cheque w/d Paul Richard (v)', 202.00, False),
    ('2013-12-09', 'Cheque dd Cooperators CSI', 128.33, False),
    ('2013-12-09', 'Cheque dd Bank Charges & Int...', 1.50, False),
    ('2013-12-10', 'Cheque dd Ace Truck', 2720.04, False),
    ('2013-12-10', 'Bill Pmt-Cheque dd Automotive Universe', 1043.11, False),
    ('2013-12-11', 'Cheque w/d Paul Richard (v)', 200.00, False),
    ('2013-12-11', 'Cheque dd Fas Gas Plus', 151.00, False),
    ('2013-12-12', 'Bill Pmt-Cheque dd Tire Garage', 673.05, False),
    ('2013-12-13', 'Cheque dd Liquor Barn', 863.37, False),
    ('2013-12-13', 'Cheque dd Fas Gas Plus', 50.00, False),
    ('2013-12-14', 'Cheque w/d Paul Richard (v)', 300.00, False),
    ('2013-12-14', 'Cheque dd Fas Gas Plus', 165.91, False),
    ('2013-12-15', 'Cheque dd Future Shop Red Deer', 360.97, False),
    ('2013-12-15', 'Cheque dd Cellcom Wireless Inc', 88.73, False),
    ('2013-12-16', 'Cheque dd Heffner Lexus Toyota', 3181.17, False),
    ('2013-12-16', 'Cheque dd Heffner Lexus Toyota', 2525.25, False),
    ('2013-12-16', 'Cheque dd Heffner Lexus Toyota', 1900.50, False),
    ('2013-12-16', 'Cheque dd Heffner Lexus Toyota', 889.88, False),
    ('2013-12-16', 'Cheque dd Heffner Lexus Toyota', 738.41, False),
    ('2013-12-18', 'Bill Pmt-Cheque 283 Big 105', 1260.00, False),
    ('2013-12-18', 'Cheque dd ATR Logistics', 550.73, False),
    ('2013-12-18', 'Cheque 284 Jonathan Korsh', 500.00, False),
    ('2013-12-18', 'Cheque dd Walmart', 52.79, False),
    ('2013-12-18', 'Cheque dd Co-op', 40.00, False),
    ('2013-12-18', 'Cheque dd Red Deer Registries', 704.35, False),
    ('2013-12-19', 'Cheque dd Red Deer Registries', 392.35, False),
    ('2013-12-19', 'Cheque dd Toys R Us', 145.87, False),
    ('2013-12-19', 'Cheque dd Canadian Tire.', 123.45, False),
    ('2013-12-19', 'Cheque dd Sushi Sushi', 35.31, False),
    ('2013-12-19', 'Cheque dd Co-op', 4.82, False),
    ('2013-12-20', 'Cheque dd Equity Premium Fin...', 1157.94, False),
    ('2013-12-20', 'Cheque 286 Larry Taylor', 519.75, False),
    ('2013-12-20', 'Bill Pmt-Cheque dd Eries Auto Repair', 265.92, False),
    ('2013-12-20', 'Cheque w/d Paul Richard (v)', 202.00, False),
    ('2013-12-20', 'Cheque w/d Paul Richard (v)', 201.85, False),
    ('2013-12-20', 'Bill Pmt-Cheque dd Choice Auto Electric...', 137.35, False),
    ('2013-12-20', 'Cheque dd Centex', 61.00, False),
    ('2013-12-20', 'Cheque dd PartsSource', 32.93, False),
    ('2013-12-20', 'Cheque dd Bank Charges & Int...', 1.50, False),
    ('2013-12-21', 'Cheque dd Fas Gas Plus', 77.50, False),
    ('2013-12-21', 'Cheque dd Canadian Tire.', 64.38, False),
    ('2013-12-22', 'Cheque dd Petro Canada', 170.02, False),
    ('2013-12-23', 'Cheque dd Safeway', 300.00, False),
    ('2013-12-23', 'Cheque 287 Michael Richard', 300.00, False),
    ('2013-12-23', 'Cheque dd Shoppers Drug Mart', 77.96, False),
    ('2013-12-27', 'Bill Pmt-Cheque 288 Fibrenew', 1706.25, False),
    ('2013-12-27', 'Bill Pmt-Cheque dd Telus Communicatio...', 1655.63, False),
    ('2013-12-27', 'Cheque dd Paul Richard (v)', 1500.00, False),
    ('2013-12-27', 'Bill Pmt-Cheque dd WCB', 1124.23, False),
    ('2013-12-27', 'Bill Pmt-Cheque dd Telus Communicatio...', 1077.45, False),
    ('2013-12-27', 'Bill Pmt-Cheque dd Rogers', 740.17, False),
    ('2013-12-27', 'Bill Pmt-Cheque dd Rogers', 740.17, False),
    ('2013-12-27', 'Cheque dd Capital One MC', 500.00, False),
    ('2013-12-27', 'Cheque dd Berglund, Louise', 500.00, False),
    ('2013-12-27', 'Bill Pmt-Cheque 289 Fibrenew', 492.26, False),
    ('2013-12-27', 'Bill Pmt-Cheque dd Telus Communicatio...', 378.35, False),
    ('2013-12-27', 'Cheque w/d Paul Richard (v)', 200.00, False),
    ('2013-12-27', 'Cheque dd Telus Mobility', 121.79, False),
    ('2013-12-27', 'Cheque dd Fas Gas Plus', 29.00, False),
    ('2013-12-28', 'Cheque w/d Paul Richard (v)', 1000.00, False),
    ('2013-12-30', 'Cheque w/d Paul Richard (v)', 1000.00, False),
    ('2013-12-30', 'Cheque w/d Paul Richard (v)', 700.00, False),
    ('2013-12-30', 'Cheque dd ScotiaBank Value Vi...', 600.00, False),
    ('2013-12-30', 'Cheque dd LFG Business PAD', 405.66, False),
    ('2013-12-30', 'Cheque dd Bank Charges & Int...', 7.50, False),
    ('2013-12-31', 'Cheque w/d Paul Richard (v)', 1200.00, False),
    ('2013-12-31', 'Cheque dd Bank Charges & Int...', 117.73, False),
    
    # Deposits (credits)
    ('2013-12-30', 'Deposit', 3155.00, True),
    ('2013-12-31', 'Deposit', 63324.91, True),
]

def get_conn():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***')
    )

def generate_hash(date_str, description, amount):
    """Generate deterministic hash for transaction."""
    hash_input = f"{date_str}|{description}|{amount}".encode('utf-8')
    return hashlib.sha256(hash_input).hexdigest()

def main():
    print("\n" + "="*80)
    print("IMPORT SCOTIA BANK DECEMBER 2013 CLEARED TRANSACTIONS")
    print("="*80)
    print(f"Account: {ACCOUNT}")
    print(f"Mode: {'DRY RUN' if DRY_RUN else 'WRITE'}")
    print(f"Total transactions: {len(SCOTIA_DEC_2013)}")
    
    conn = get_conn()
    cur = conn.cursor()
    
    # Check existing data
    cur.execute("""
        SELECT COUNT(*) FROM banking_transactions
        WHERE account_number = %s 
        AND transaction_date >= '2013-12-01' 
        AND transaction_date <= '2013-12-31'
    """, (ACCOUNT,))
    existing_count = cur.fetchone()[0]
    
    print(f"\nExisting Dec 2013 Scotia transactions in DB: {existing_count}")
    
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
    
    for txn_date, description, amount, is_deposit in SCOTIA_DEC_2013:
        debit = None if is_deposit else amount
        credit = amount if is_deposit else None
        source_hash = generate_hash(txn_date, description, amount)
        
        if source_hash in existing_hashes:
            skipped.append((txn_date, description, amount))
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
    print(f"Beginning balance: -$4,480.57")
    print(f"Expected ending balance: $6,404.87")
    
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
    
    # Verify Scotia Bank data
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
    print(f"SCOTIA BANK 2013 SUMMARY")
    print(f"{'='*80}")
    print(f"Total 2013 transactions: {total_count}")
    print(f"Date range: {first_date} to {last_date}")
    print(f"Total debits: ${float(total_debits_db or 0):,.2f}")
    print(f"Total credits: ${float(total_credits_db or 0):,.2f}")
    print(f"Net change: ${float(total_credits_db or 0) - float(total_debits_db or 0):+,.2f}")
    
    cur.close()
    conn.close()
    
    print("\n" + "="*80)

if __name__ == '__main__':
    main()
