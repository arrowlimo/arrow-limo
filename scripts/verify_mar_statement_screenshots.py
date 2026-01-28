#!/usr/bin/env python3
"""
Verify all transactions from CIBC statement screenshots (Mar 15-31, 2012) 
are in the database.
"""

import psycopg2
import os
from datetime import datetime

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***')
    )

def check_transaction(cur, date, description, amount, tx_type, balance):
    """Check if a specific transaction exists in database."""
    
    # Try exact match first
    if tx_type == 'W':  # Withdrawal
        cur.execute("""
            SELECT transaction_id, description, debit_amount, balance
            FROM banking_transactions
            WHERE account_number = '0228362'
            AND transaction_date = %s
            AND ABS(COALESCE(debit_amount, 0) - %s) < 0.01
            ORDER BY transaction_id
        """, (date, amount))
    else:  # Deposit
        cur.execute("""
            SELECT transaction_id, description, credit_amount, balance
            FROM banking_transactions
            WHERE account_number = '0228362'
            AND transaction_date = %s
            AND ABS(COALESCE(credit_amount, 0) - %s) < 0.01
            ORDER BY transaction_id
        """, (date, amount))
    
    results = cur.fetchall()
    return results

def main():
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("=" * 100)
    print("CIBC STATEMENT VERIFICATION - MAR 15-31, 2012")
    print("=" * 100)
    print()
    
    # Transactions from screenshot pages (Mar 15-31, 2012)
    transactions = [
        # Mar 15
        ('2012-03-15', 'Balance forward', None, None, 2655.69),
        ('2012-03-15', 'PURCHASE#000001001194 VRT CAR AUDIO', 262.50, 'W', 2393.19),
        ('2012-03-15', 'RENT/LEASE LMFTR 36', 1885.65, 'W', 507.54),
        ('2012-03-15', 'RENT/LEASE HEFFNER AUTO TC', 2525.25, 'W', -2017.71),
        ('2012-03-15', 'RENT/LEASE HEFFNER AUTO TC', 1475.25, 'W', -3492.96),
        ('2012-03-15', 'RENT/LEASE HEFFNER AUTO TC', 1900.50, 'W', -5393.46),
        ('2012-03-15', 'CORRECTION 00339', 1425.25, 'D', -3968.21),
        ('2012-03-15', 'CORRECTION 00339', 1900.60, 'D', -2067.61),
        ('2012-03-15', 'CORRECTION 00339', 2525.25, 'D', 457.64),
        ('2012-03-15', 'CORRECTION 00339', None, 'D', 380.04),  # Can't see amount
        ('2012-03-15', 'NSF CHARGE 00339', 127.50, 'W', 380.04),
        
        # Mar 16
        ('2012-03-16', 'MISC PAYMENT AMEX 9320382063', 1181.04, 'D', 1561.08),
        ('2012-03-16', 'CREDIT MEMO 4017775 VISA', 550.00, 'D', 2111.08),
        ('2012-03-16', 'CREDIT MEMO 4017775 VISA', 200.00, 'D', 2311.08),
        ('2012-03-16', 'CREDIT MEMO 4017775 VISA', 705.00, 'D', 3016.08),
        ('2012-03-16', 'INSURANCE OPTIMUM WEST INSURANCE COMPANY', 83.46, 'W', 2932.62),
        
        # Mar 19
        ('2012-03-19', 'Balance forward', None, None, 2894.74),
        ('2012-03-19', 'PURCHASE#000001196026 FAS GAS NORTHSI', 80.97, 'W', 2813.77),
        ('2012-03-19', 'ABM WITHDRAWAL 2C03 INTERAC/RBC SCD 09502', 201.75, 'W', 2612.02),
        ('2012-03-19', 'CREDIT MEMO 4017775 VISA', 250.00, 'D', 2862.02),
        ('2012-03-19', 'PURCHASE#000001555004 PLAZA LIQUOR TO', 33.12, 'W', 2828.90),
        ('2012-03-19', 'PURCHASE#000001010055 CENTEX DEERPARK', 53.00, 'W', 2775.90),
        ('2012-03-19', 'NETWORK TRANS FEE INSTANT TELLER', 1.50, 'W', 2774.40),
        ('2012-03-19', 'Cheque 216 000000017190440', 100.00, 'W', 2674.40),
        ('2012-03-19', 'Cheque 215 000000017416990', 150.00, 'W', 2524.40),
        
        # Mar 20
        ('2012-03-20', 'E-TRANSFER#000000048957179 Will Heffner', 2000.00, 'W', 524.40),
        ('2012-03-20', 'CREDIT MEMO 4017775 IDP', 82.50, 'D', 606.90),
        ('2012-03-20', 'CREDIT MEMO 4017775 VISA', 438.50, 'D', 1045.40),
        ('2012-03-20', 'CREDIT MEMO 4017775 VISA', 625.00, 'D', 1670.40),
        ('2012-03-20', 'CREDIT MEMO 4017775 MC', 140.00, 'D', 1810.40),
        ('2012-03-20', 'DEPOSIT', 95.91, 'D', 1906.31),
        ('2012-03-20', 'DEPOSIT', 200.00, 'D', 2106.31),
        
        # Mar 21
        ('2012-03-21', 'CREDIT MEMO 4017775 MC', 250.00, 'D', 2356.31),
        ('2012-03-21', 'CREDIT MEMO 4017775 VISA', 500.00, 'D', 2956.31),
        ('2012-03-21', 'CREDIT MEMO 4017775 VISA', 120.00, 'D', 3076.31),
        ('2012-03-21', 'E-TRANSFER#000003660128 Will Heffner', 2000.00, 'W', 1076.31),
        ('2012-03-21', 'ABM WITHDRAWAL 2CQ0 7-ELEVEN 99512', 700.00, 'W', 376.31),
        
        # Mar 22
        ('2012-03-22', 'CREDIT MEMO 4017775 MC', 637.00, 'D', 1013.31),
        ('2012-03-22', 'CREDIT MEMO 4017775 VISA', 200.00, 'D', 1213.31),
        ('2012-03-22', 'DEPOSIT', 600.00, 'D', 1813.31),
        ('2012-03-22', 'E-TRANSFER#000003263084 Will Heffner', 940.00, 'W', 873.31),
        
        # Mar 23
        ('2012-03-23', 'MISC PAYMENT AMEX 9320382063', 256.35, 'D', 1129.66),
        ('2012-03-23', 'ABM WITHDRAWAL 2CQ0 7-ELEVEN 99512', 100.00, 'W', 1029.66),
        
        # Mar 26
        ('2012-03-26', 'MISC PAYMENT AMEX 9320383061', 2030.11, 'D', 3059.77),
        ('2012-03-26', 'PURCHASE#205001001017 JIMBO CAR WASH', 100.00, 'W', 2959.77),
        ('2012-03-26', 'PURCHASE#000001214016 CENTEX DEERPARK', 188.98, 'W', 2770.79),
        ('2012-03-26', 'CREDIT MEMO 4017775 VISA', 205.00, 'D', 2975.79),
        ('2012-03-26', 'MISC PAYMENT AMEX 9320383061', 1073.08, 'D', 4048.87),
        ('2012-03-26', 'DEPOSIT', 600.00, 'D', 4648.87),
        ('2012-03-26', 'INSURANCE JEVCO INSURANCE COMPANY', 268.92, 'W', 4379.95),
        ('2012-03-26', 'INSURANCE IFS PREMIUM FIN', 1271.47, 'W', 3108.48),
        ('2012-03-26', 'INSURANCE CO-OPERATORS', 110.42, 'W', 2998.06),
        
        # Mar 27
        ('2012-03-27', 'CREDIT MEMO 4017775 MC', 477.00, 'D', 3475.06),
        ('2012-03-27', 'CREDIT MEMO 4017775 MC', 231.00, 'D', 3706.06),
        ('2012-03-27', 'CREDIT MEMO 4017775 VISA', 205.00, 'D', 3911.06),
        
        # Mar 28
        ('2012-03-28', 'CREDIT MEMO 4017775 MC', 675.00, 'D', 4068.06),
        ('2012-03-28', 'CREDIT MEMO 4017775 VISA', 663.70, 'D', 4731.76),
        ('2012-03-28', 'MISC PAYMENT AMEX 9320383063', None, 'W', 4726.81),  # Can't see exact amount
        
        # Mar 29
        ('2012-03-29', 'CREDIT MEMO 4017775 VISA', 100.00, 'D', 4826.81),
        ('2012-03-29', 'CREDIT MEMO 4017775 VISA', 50.00, 'D', 4876.81),
        ('2012-03-29', 'CREDIT MEMO 4017775 VISA', 93.75, 'D', 4970.56),
        ('2012-03-29', 'E-TRANSFER C TO: 00339M2-28362', 2000.00, 'W', 2970.56),
        ('2012-03-29', 'DEBIT MEMO CASH', 2200.00, 'W', 770.56),
        
        # Mar 30
        ('2012-03-30', 'CREDIT MEMO 4017775 MC', 205.00, 'D', 975.56),
        ('2012-03-30', 'E-TRANSFER NWK FEE', None, 'W', 974.05),  # Small fee, can't see exact
        ('2012-03-30', 'ACCOUNT FEE', None, 'W', 939.06),  # Can't see exact
        
        # Mar 31 closing
        ('2012-03-31', 'Closing balance', None, None, 939.06),
    ]
    
    total = 0
    found = 0
    missing = 0
    
    for tx in transactions:
        date, desc, amount, tx_type, balance = tx
        
        if amount is None or tx_type is None:
            continue  # Skip balance forward/closing balance lines
        
        total += 1
        results = check_transaction(cur, date, desc, amount, tx_type, balance)
        
        if results:
            found += 1
            print(f"[OK] {date} | {tx_type} ${amount:>8.2f} | {desc[:50]}")
        else:
            missing += 1
            print(f"[FAIL] {date} | {tx_type} ${amount:>8.2f} | {desc[:50]} | Balance: ${balance:.2f}")
    
    print()
    print("=" * 100)
    print(f"SUMMARY:")
    print(f"Total transactions checked: {total}")
    print(f"Found in database: {found} ({found/total*100:.1f}%)")
    print(f"Missing from database: {missing} ({missing/total*100:.1f}%)")
    print("=" * 100)
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
