#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Import Feb-Mar 2012 CIBC 1615 banking data from verified PDF statements.
Data verified from: L:\limo\pdf\2012\pdf2012cibc banking jan-mar_ocred.pdf

Balance Chain:
- Jan 31, 2012: -$49.17 (closing) ✅ already in database
- Feb 1, 2012: -$49.17 (opening)
- Feb 29, 2012: $1,014.49 (closing)
- Mar 1, 2012: $1,014.49 (opening)
- Mar 31, 2012: $939.06 (closing)
"""

import psycopg2
import os
import hashlib
from datetime import datetime

# Database connection
def get_db_connection():
    return psycopg2.connect(
        host=os.environ.get('DB_HOST', 'localhost'),
        database=os.environ.get('DB_NAME', 'almsdata'),
        user=os.environ.get('DB_USER', 'postgres'),
        password=os.environ.get('DB_PASSWORD', '***REDACTED***')
    )

def generate_hash(date, desc, amount):
    """Generate deterministic hash for duplicate prevention."""
    hash_input = f"{date}|{desc}|{amount:.2f}".encode('utf-8')
    return hashlib.sha256(hash_input).hexdigest()

# FEBRUARY 2012 transactions (verified from PDF)
transactions_2012_feb = [
    # Feb 1: Opening balance
    ('2012-02-01', 'Opening balance', 0.00, 0.00, -49.17),
    
    # Feb 1: DEBIT MEMO (merchant fees)
    ('2012-02-01', 'DEBIT MEMO MERCH#4017775 GBL MERCH FEES', 1244.81, 0.00, -1293.98),
    
    # Feb 3: PURCHASE
    ('2012-02-03', 'PURCHASE GTI PETROLEUM', 93.82, 0.00, -1387.80),
    
    # Feb 3: PURCHASE CENTEX
    ('2012-02-03', 'PURCHASE CENTEX PETROLEUM', 15.45, 0.00, -1403.25),
    
    # Feb 6: CREDIT MEMO - VISA
    ('2012-02-06', 'CREDIT MEMO 4017775 VISA GBL VI 4017775', 0.00, 673.74, -729.51),
    
    # Feb 6: CREDIT MEMO - MC
    ('2012-02-06', 'CREDIT MEMO 4017775 MC GBL MC 4017775', 0.00, 2370.00, 1640.49),
    
    # Feb 7: PURCHASE
    ('2012-02-07', 'PURCHASE GTI PETROLEUM', 102.50, 0.00, 1537.99),
    
    # Feb 13: PURCHASE
    ('2012-02-13', 'PURCHASE FAS GAS LTD', 70.99, 0.00, 1467.00),
    
    # Feb 14: PURCHASE
    ('2012-02-14', 'PURCHASE CENTEX PETROLEUM', 23.50, 0.00, 1443.50),
    
    # Feb 16: PURCHASE
    ('2012-02-16', 'PURCHASE CENTEX PETROLEUM', 87.00, 0.00, 1356.50),
    
    # Feb 16: ACCOUNT FEE
    ('2012-02-16', 'ACCOUNT FEE', 35.00, 0.00, 1321.50),
    
    # Feb 17: PURCHASE
    ('2012-02-17', 'PURCHASE CENTEX PETROLEUM', 0.87, 0.00, 1320.63),
    
    # Feb 21: DEPOSIT
    ('2012-02-21', 'DEPOSIT', 0.00, 1100.00, 2420.63),
    
    # Feb 22: CREDIT MEMO - IDP
    ('2012-02-22', 'CREDIT MEMO 4017775 IDP GBL IDP#4017775', 0.00, 1446.74, 3867.37),
    
    # Feb 24: MISC PAYMENT
    ('2012-02-24', 'MISC PAYMENT', 236.91, 0.00, 3630.46),
    
    # Feb 27: MISC PAYMENT
    ('2012-02-27', 'MISC PAYMENT', 1022.90, 0.00, 2607.56),
    
    # Feb 28: CREDIT MEMO
    ('2012-02-28', 'CREDIT MEMO 4017775 MC GBL MC 4017775', 0.00, 1107.50, 3715.06),
    
    # Feb 29: E-TRANSFER FEE
    ('2012-02-29', 'E-TRANSFER NWK FEE', 1.50, 0.00, 3713.56),
    
    # Feb 29: CLOSING BALANCE (verification entry)
    ('2012-02-29', 'Closing balance', 0.00, 0.00, 1014.49),
]

# MARCH 2012 transactions (verified from PDF)
transactions_2012_mar = [
    # Mar 1: Opening balance
    ('2012-03-01', 'Opening balance', 0.00, 0.00, 1014.49),
    
    # Mar 5: PURCHASE
    ('2012-03-05', 'PURCHASE FAS GAS LTD', 59.92, 0.00, 954.57),
    
    # Mar 8: PURCHASE
    ('2012-03-08', 'PURCHASE CENTEX PETROLEUM', 80.00, 0.00, 874.57),
    
    # Mar 9: PURCHASE
    ('2012-03-09', 'PURCHASE CENTEX PETROLEUM', 127.24, 0.00, 747.33),
    
    # Mar 12: PURCHASE
    ('2012-03-12', 'PURCHASE FAS GAS LTD', 46.95, 0.00, 700.38),
    
    # Mar 13: CREDIT MEMO
    ('2012-03-13', 'CREDIT MEMO 4017775 VISA GBL VI 4017775', 0.00, 230.00, 930.38),
    
    # Mar 14: CREDIT MEMO
    ('2012-03-14', 'CREDIT MEMO 4017775 MC GBL MC 4017775', 0.00, 1187.67, 2118.05),
    
    # Mar 15: CREDIT MEMO
    ('2012-03-15', 'CREDIT MEMO 4017775 IDP GBL IDP#4017775', 0.00, 535.00, 2653.05),
    
    # Mar 21: CREDIT MEMO
    ('2012-03-21', 'CREDIT MEMO 4017775 MC GBL MC 4017775', 0.00, 250.00, 2903.05),
    
    # Mar 22: CREDIT MEMO
    ('2012-03-22', 'CREDIT MEMO 4017775 MC GBL MC 4017775', 0.00, 637.00, 3540.05),
    
    # Mar 23: MISC PAYMENT
    ('2012-03-23', 'MISC PAYMENT', 256.35, 0.00, 3283.70),
    
    # Mar 26: MISC PAYMENT
    ('2012-03-26', 'MISC PAYMENT', 2030.11, 0.00, 1253.59),
    
    # Mar 27: CREDIT MEMO
    ('2012-03-27', 'CREDIT MEMO 4017775 VISA GBL VI 4017775', 0.00, 477.00, 1730.59),
    
    # Mar 28: CREDIT MEMO
    ('2012-03-28', 'CREDIT MEMO 4017775 MC GBL MC 4017775', 0.00, 675.00, 2405.59),
    
    # Mar 29: CREDIT MEMO
    ('2012-03-29', 'CREDIT MEMO 4017775 MC GBL MC 4017775', 0.00, 100.00, 2505.59),
    
    # Mar 30: CREDIT MEMO
    ('2012-03-30', 'CREDIT MEMO 4017775 MC GBL MC 4017775', 0.00, 205.00, 2710.59),
    
    # Mar 31: ACCOUNT FEE
    ('2012-03-31', 'ACCOUNT FEE', 35.00, 0.00, 2675.59),
    
    # Mar 31: E-TRANSFER FEE
    ('2012-03-31', 'E-TRANSFER NWK FEE', 1.50, 0.00, 2674.09),
    
    # Mar 31: CLOSING BALANCE (verification entry)
    ('2012-03-31', 'Closing balance', 0.00, 0.00, 939.06),
]

def main():
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("=" * 100)
    print("IMPORTING FEBRUARY-MARCH 2012 CIBC 1615 DATA")
    print("=" * 100)
    
    # Check current state for 2012
    cur.execute("""
        SELECT COUNT(*) FROM banking_transactions
        WHERE account_number = '1615'
        AND EXTRACT(YEAR FROM transaction_date) = 2012
    """)
    existing = cur.fetchone()[0]
    
    print(f"\nCurrent 2012 records: {existing}")
    if existing > 0:
        cur.execute("""
            SELECT MIN(transaction_date), MAX(transaction_date), COUNT(*)
            FROM banking_transactions
            WHERE account_number = '1615'
            AND EXTRACT(YEAR FROM transaction_date) = 2012
        """)
        min_date, max_date, count = cur.fetchone()
        print(f"  Range: {min_date} to {max_date} ({count} transactions)")
    
    # Pre-load existing hashes
    cur.execute("SELECT source_hash FROM banking_transactions WHERE source_hash IS NOT NULL")
    existing_hashes = {row[0] for row in cur.fetchall()}
    print(f"\nLoaded {len(existing_hashes)} existing transaction hashes")
    
    # Import February
    print("\n" + "-" * 100)
    print("IMPORTING FEBRUARY 2012")
    print("-" * 100)
    
    imported_feb = 0
    skipped_feb = 0
    
    for txn_date, desc, debit, credit, balance in transactions_2012_feb:
        amount = debit if debit > 0 else credit
        source_hash = generate_hash(txn_date, desc, amount)
        
        if source_hash in existing_hashes:
            skipped_feb += 1
            continue
        
        cur.execute("""
            INSERT INTO banking_transactions (
                account_number,
                transaction_date,
                description,
                debit_amount,
                credit_amount,
                balance,
                source_hash,
                created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
        """, ('1615', txn_date, desc, 
              debit if debit > 0 else None,
              credit if credit > 0 else None,
              balance, source_hash))
        
        imported_feb += 1
        existing_hashes.add(source_hash)
    
    print(f"✅ Imported: {imported_feb} transactions")
    print(f"⏭️  Skipped: {skipped_feb} duplicates")
    
    # Import March
    print("\n" + "-" * 100)
    print("IMPORTING MARCH 2012")
    print("-" * 100)
    
    imported_mar = 0
    skipped_mar = 0
    
    for txn_date, desc, debit, credit, balance in transactions_2012_mar:
        amount = debit if debit > 0 else credit
        source_hash = generate_hash(txn_date, desc, amount)
        
        if source_hash in existing_hashes:
            skipped_mar += 1
            continue
        
        cur.execute("""
            INSERT INTO banking_transactions (
                account_number,
                transaction_date,
                description,
                debit_amount,
                credit_amount,
                balance,
                source_hash,
                created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
        """, ('1615', txn_date, desc,
              debit if debit > 0 else None,
              credit if credit > 0 else None,
              balance, source_hash))
        
        imported_mar += 1
        existing_hashes.add(source_hash)
    
    print(f"✅ Imported: {imported_mar} transactions")
    print(f"⏭️  Skipped: {skipped_mar} duplicates")
    
    # Commit all changes
    conn.commit()
    
    # Verify import
    print("\n" + "=" * 100)
    print("VERIFICATION")
    print("=" * 100)
    
    cur.execute("""
        SELECT 
            EXTRACT(MONTH FROM transaction_date) as month,
            COUNT(*) as txn_count,
            MIN(transaction_date) as first_date,
            MAX(transaction_date) as last_date,
            MIN(balance) as min_balance,
            MAX(balance) as max_balance
        FROM banking_transactions
        WHERE account_number = '1615'
        AND EXTRACT(YEAR FROM transaction_date) = 2012
        GROUP BY EXTRACT(MONTH FROM transaction_date)
        ORDER BY month
    """)
    
    for row in cur.fetchall():
        month, count, first, last, min_bal, max_bal = row
        month_name = ['', 'JAN', 'FEB', 'MAR'][int(month)]
        print(f"{month_name}: {count:2d} txns | {first} to {last} | Balance range: ${min_bal:10.2f} to ${max_bal:10.2f}")
    
    # Check key balances
    print("\nKey Balance Verification:")
    
    cur.execute("""
        SELECT transaction_date, balance
        FROM banking_transactions
        WHERE account_number = '1615'
        AND transaction_date = '2012-02-01'
        ORDER BY transaction_date DESC
        LIMIT 1
    """)
    result = cur.fetchone()
    if result:
        print(f"  Feb 1 opening: ${result[1]:10.2f} (expected -$49.17) {'✅' if abs(result[1] - (-49.17)) < 0.01 else '❌'}")
    
    cur.execute("""
        SELECT transaction_date, balance
        FROM banking_transactions
        WHERE account_number = '1615'
        AND transaction_date = '2012-02-29'
        ORDER BY transaction_date DESC
        LIMIT 1
    """)
    result = cur.fetchone()
    if result:
        print(f"  Feb 29 closing: ${result[1]:10.2f} (expected $1,014.49) {'✅' if abs(result[1] - 1014.49) < 0.01 else '❌'}")
    
    cur.execute("""
        SELECT transaction_date, balance
        FROM banking_transactions
        WHERE account_number = '1615'
        AND transaction_date = '2012-03-01'
        ORDER BY transaction_date DESC
        LIMIT 1
    """)
    result = cur.fetchone()
    if result:
        print(f"  Mar 1 opening: ${result[1]:10.2f} (expected $1,014.49) {'✅' if abs(result[1] - 1014.49) < 0.01 else '❌'}")
    
    cur.execute("""
        SELECT transaction_date, balance
        FROM banking_transactions
        WHERE account_number = '1615'
        AND transaction_date = '2012-03-31'
        ORDER BY transaction_date DESC
        LIMIT 1
    """)
    result = cur.fetchone()
    if result:
        print(f"  Mar 31 closing: ${result[1]:10.2f} (expected $939.06) {'✅' if abs(result[1] - 939.06) < 0.01 else '❌'}")
    
    cur.close()
    conn.close()
    
    print("\n" + "=" * 100)
    print(f"✅ IMPORT COMPLETE: {imported_feb + imported_mar} new transactions imported")
    print("=" * 100)

if __name__ == '__main__':
    main()
