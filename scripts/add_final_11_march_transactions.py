#!/usr/bin/env python3
"""
Add the final 11 missing March transactions - these are duplicates with different descriptions.
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
        password=os.getenv('DB_PASSWORD', '***REMOVED***')
    )

def main():
    write_mode = len(sys.argv) > 1 and sys.argv[1] == '--write'
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    account_number = '0228362'
    
    # The remaining 11 transactions - multiple CREDIT MEMOs on same days
    transactions = [
        ('2012-03-15', 'CORRECTION 00339', None, 1425.25, -3968.21),
        ('2012-03-15', 'CORRECTION 00339', None, 1900.60, -2067.61),
        ('2012-03-16', 'CREDIT MEMO 4017775 VISA GBL VI 4017775', None, 200.00, 2311.08),
        ('2012-03-16', 'CREDIT MEMO 4017775 VISA GBL VI 4017775', None, 705.00, 3016.08),
        ('2012-03-20', 'CREDIT MEMO 4017775 VISA GBL VI 4017775', None, 625.00, 1670.40),
        ('2012-03-20', 'DEPOSIT', None, 200.00, 2106.31),
        ('2012-03-21', 'CREDIT MEMO 4017775 VISA GBL VI 4017775', None, 120.00, 3076.31),
        ('2012-03-26', 'MISC PAYMENT AMEX 9320383061', None, 1073.08, 4048.87),
        ('2012-03-27', 'CREDIT MEMO 4017775 MC GBL MC 4017775', None, 231.00, 3706.06),
        ('2012-03-29', 'CREDIT MEMO 4017775 VISA GBL VI 4017775', None, 50.00, 4876.81),
        ('2012-03-29', 'CREDIT MEMO 4017775 VISA GBL VI 4017775', None, 93.75, 4970.56),
    ]
    
    added = 0
    
    for tx_date, description, debit, credit, balance in transactions:
        # Check for exact match including balance
        cur.execute("""
            SELECT transaction_id FROM banking_transactions
            WHERE account_number = %s
            AND transaction_date = %s
            AND description = %s
            AND COALESCE(credit_amount, 0) = %s
            AND ABS(COALESCE(balance, 0) - %s) < 0.01
        """, (account_number, tx_date, description, credit or 0, balance))
        
        if cur.fetchone():
            print(f"[WARN]  SKIP: {tx_date} | ${credit:.2f} | {description[:50]} (already exists)")
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
            amount = credit or debit
            print(f"[OK] ADD: {tx_date} | D ${amount:>8.2f} | {description[:50]} → ID {new_id}")
            added += 1
        else:
            amount = credit or debit
            print(f"[OK] WILL ADD: {tx_date} | D ${amount:>8.2f} | {description[:50]}")
            added += 1
    
    if write_mode:
        conn.commit()
        print(f"\n[OK] Successfully added {added} transactions")
    else:
        print(f"\n[WARN]  DRY RUN: Would add {added} transactions")
        print("Run with --write to apply changes")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
