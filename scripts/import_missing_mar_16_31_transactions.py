#!/usr/bin/env python3
"""
Import missing Mar 15-31, 2012 transactions from CIBC statement screenshots.
This will add all 51 missing transactions to the database.
"""

import psycopg2
import os
import sys
from datetime import datetime

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REDACTED***')
    )

def main():
    write_mode = len(sys.argv) > 1 and sys.argv[1] == '--write'
    
    if not write_mode:
        print("=" * 100)
        print("DRY RUN MODE - Add --write to actually insert transactions")
        print("=" * 100)
    else:
        print("=" * 100)
        print("WRITE MODE - Will insert missing transactions")
        print("=" * 100)
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    account_number = '0228362'
    
    # All transactions from CIBC statement screenshots Mar 15-31, 2012
    transactions = [
        # Mar 15 - Only missing the CORRECTIONS
        ('2012-03-15', 'CORRECTION 00339', None, 1425.25, -3968.21),
        ('2012-03-15', 'CORRECTION 00339', None, 1900.60, -2067.61),
        
        # Mar 16 - ALL missing
        ('2012-03-16', 'MISC PAYMENT AMEX 9320382063', None, 1181.04, 1561.08),
        ('2012-03-16', 'CREDIT MEMO 4017775 VISA GBL VI 4017775', None, 550.00, 2111.08),
        ('2012-03-16', 'CREDIT MEMO 4017775 VISA GBL VI 4017775', None, 200.00, 2311.08),
        ('2012-03-16', 'CREDIT MEMO 4017775 VISA GBL VI 4017775', None, 705.00, 3016.08),
        ('2012-03-16', 'INSURANCE OPTIMUM WEST INSURANCE COMPANY', 83.46, None, 2932.62),
        
        # Mar 19 - All except the 2 cheques we already added
        ('2012-03-19', 'PURCHASE#000001196026 FAS GAS NORTHSI 4506*********359', 80.97, None, 2813.77),
        ('2012-03-19', 'ABM WITHDRAWAL 2C03 INTERAC/RBC SCD 09502 4506*********359', 201.75, None, 2612.02),
        ('2012-03-19', 'CREDIT MEMO 4017775 VISA GBL VI 4017775', None, 250.00, 2862.02),
        ('2012-03-19', 'PURCHASE#000001555004 PLAZA LIQUOR TO 4506*********359', 33.12, None, 2828.90),
        ('2012-03-19', 'PURCHASE#000001010055 CENTEX DEERPARK 4506*********359', 53.00, None, 2775.90),
        ('2012-03-19', 'NETWORK TRANS FEE INSTANT TELLER', 1.50, None, 2774.40),
        
        # Mar 20 - ALL missing
        ('2012-03-20', 'E-TRANSFER#000000048957179 Will Heffner 4506*********359', 2000.00, None, 524.40),
        ('2012-03-20', 'CREDIT MEMO 4017775 IDP GBL IDP#4017775', None, 82.50, 606.90),
        ('2012-03-20', 'CREDIT MEMO 4017775 VISA GBL VI 4017775', None, 438.50, 1045.40),
        ('2012-03-20', 'CREDIT MEMO 4017775 VISA GBL VI 4017775', None, 625.00, 1670.40),
        ('2012-03-20', 'CREDIT MEMO 4017775 MC GBL MC 4017775', None, 140.00, 1810.40),
        ('2012-03-20', 'DEPOSIT', None, 95.91, 1906.31),
        ('2012-03-20', 'DEPOSIT', None, 200.00, 2106.31),
        
        # Mar 21 - ALL missing
        ('2012-03-21', 'CREDIT MEMO 4017775 MC GBL MC 4017775', None, 250.00, 2356.31),
        ('2012-03-21', 'CREDIT MEMO 4017775 VISA GBL VI 4017775', None, 500.00, 2956.31),
        ('2012-03-21', 'CREDIT MEMO 4017775 VISA GBL VI 4017775', None, 120.00, 3076.31),
        ('2012-03-21', 'E-TRANSFER#000003660128 Will Heffner 4506*********359', 2000.00, None, 1076.31),
        ('2012-03-21', 'ABM WITHDRAWAL 2CQ0 7-ELEVEN 99512 4506*********359', 700.00, None, 376.31),
        
        # Mar 22 - ALL missing
        ('2012-03-22', 'CREDIT MEMO 4017775 MC GBL MC 4017775', None, 637.00, 1013.31),
        ('2012-03-22', 'CREDIT MEMO 4017775 VISA GBL VI 4017775', None, 200.00, 1213.31),
        ('2012-03-22', 'DEPOSIT', None, 600.00, 1813.31),
        ('2012-03-22', 'E-TRANSFER#000003263084 Will Heffner 4506*********359', 940.00, None, 873.31),
        
        # Mar 23 - ALL missing
        ('2012-03-23', 'MISC PAYMENT AMEX 9320382063', None, 256.35, 1129.66),
        ('2012-03-23', 'ABM WITHDRAWAL 2CQ0 7-ELEVEN 99512 4506*********359', 100.00, None, 1029.66),
        
        # Mar 26 - ALL missing
        ('2012-03-26', 'MISC PAYMENT AMEX 9320383061', None, 2030.11, 3059.77),
        ('2012-03-26', 'PURCHASE#205001001017 JIMBO CAR WASH 4506*********359', 100.00, None, 2959.77),
        ('2012-03-26', 'PURCHASE#000001214016 CENTEX DEERPARK 4506*********359', 188.98, None, 2770.79),
        ('2012-03-26', 'CREDIT MEMO 4017775 VISA GBL VI 4017775', None, 205.00, 2975.79),
        ('2012-03-26', 'MISC PAYMENT AMEX 9320383061', None, 1073.08, 4048.87),
        ('2012-03-26', 'DEPOSIT', None, 600.00, 4648.87),
        ('2012-03-26', 'INSURANCE JEVCO INSURANCE COMPANY', 268.92, None, 4379.95),
        ('2012-03-26', 'INSURANCE IFS PREMIUM FIN', 1271.47, None, 3108.48),
        ('2012-03-26', 'INSURANCE CO-OPERATORS', 110.42, None, 2998.06),
        
        # Mar 27 - ALL missing
        ('2012-03-27', 'CREDIT MEMO 4017775 MC GBL MC 4017775', None, 477.00, 3475.06),
        ('2012-03-27', 'CREDIT MEMO 4017775 MC GBL MC 4017775', None, 231.00, 3706.06),
        ('2012-03-27', 'CREDIT MEMO 4017775 VISA GBL VI 4017775', None, 205.00, 3911.06),
        
        # Mar 28 - ALL missing
        ('2012-03-28', 'CREDIT MEMO 4017775 MC GBL MC 4017775', None, 675.00, 4068.06),
        ('2012-03-28', 'CREDIT MEMO 4017775 VISA GBL VI 4017775', None, 663.70, 4731.76),
        ('2012-03-28', 'MISC PAYMENT AMD# 932038 AMEX BANK OF CANADA', 4.95, None, 4726.81),
        
        # Mar 29 - ALL missing
        ('2012-03-29', 'CREDIT MEMO 4017775 VISA GBL VI 4017775', None, 100.00, 4826.81),
        ('2012-03-29', 'CREDIT MEMO 4017775 VISA GBL VI 4017775', None, 50.00, 4876.81),
        ('2012-03-29', 'CREDIT MEMO 4017775 VISA GBL VI 4017775', None, 93.75, 4970.56),
        ('2012-03-29', 'TRANSFER C TO: 00339M2-28362', 2000.00, None, 2970.56),
        ('2012-03-29', 'DEBIT MEMO CASH', 2200.00, None, 770.56),
        
        # Mar 30 - Missing
        ('2012-03-30', 'CREDIT MEMO 4017775 MC GBL MC 4017775', None, 205.00, 975.56),
        ('2012-03-30', 'E-TRANSFER NWK FEE', 1.50, None, 974.06),
        ('2012-03-30', 'ACCOUNT FEE', 35.00, None, 939.06),
    ]
    
    added = 0
    skipped = 0
    
    for tx_date, description, debit, credit, balance in transactions:
        # Check if already exists
        cur.execute("""
            SELECT transaction_id FROM banking_transactions
            WHERE account_number = %s
            AND transaction_date = %s
            AND description = %s
        """, (account_number, tx_date, description))
        
        if cur.fetchone():
            print(f"[WARN]  SKIP: {tx_date} | {description[:60]}")
            skipped += 1
            continue
        
        if write_mode:
            cur.execute("""
                INSERT INTO banking_transactions (
                    account_number,
                    transaction_date,
                    description,
                    debit_amount,
                    credit_amount,
                    balance,
                    created_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING transaction_id
            """, (
                account_number,
                tx_date,
                description,
                debit,
                credit,
                balance,
                datetime.now()
            ))
            
            new_id = cur.fetchone()[0]
            tx_type = 'W' if debit else 'D'
            amount = debit or credit
            print(f"[OK] ADD: {tx_date} | {tx_type} ${amount:>8.2f} | {description[:50]} → ID {new_id}")
            added += 1
        else:
            tx_type = 'W' if debit else 'D'
            amount = debit or credit
            print(f"[OK] WILL ADD: {tx_date} | {tx_type} ${amount:>8.2f} | {description[:50]}")
            added += 1
    
    if write_mode:
        conn.commit()
        print(f"\n[OK] Successfully added {added} transactions")
        print(f"[WARN]  Skipped {skipped} duplicates")
    else:
        print(f"\n[WARN]  DRY RUN: Would add {added} transactions, skip {skipped} duplicates")
        print("Run with --write to apply changes")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
