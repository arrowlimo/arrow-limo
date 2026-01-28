#!/usr/bin/env python3
"""
Check for Square reversal of $401.52 for Reserve 012219.
The dispatcher charged twice, and one was reversed in Square.
"""

import psycopg2
import os
from decimal import Decimal

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***')
    )

def main():
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("=" * 80)
    print("RESERVE 012219 - SQUARE REVERSAL ANALYSIS")
    print("=" * 80)
    
    # Find all payments with amount = +/- 401.52
    cur.execute("""
        SELECT 
            payment_id,
            amount,
            payment_date,
            payment_method,
            square_transaction_id,
            square_payment_id,
            payment_key,
            notes
        FROM payments 
        WHERE reserve_number = '012219' 
        AND ABS(amount) = 401.52
        ORDER BY payment_date, payment_id
    """)
    
    rows = cur.fetchall()
    print(f"\nPayments with amount +/- $401.52: {len(rows)} found\n")
    
    positive = []
    negative = []
    
    for r in rows:
        pid, amt, pdate, method, sq_txn, sq_pay, pkey, notes = r
        print(f"Payment {pid}: ${amt:,.2f} on {pdate}")
        print(f"  Method: {method}")
        print(f"  Square TXN: {sq_txn}")
        print(f"  Square PAY: {sq_pay}")
        print(f"  Batch Key: {pkey}")
        print(f"  Notes: {notes}")
        print()
        
        if amt > 0:
            positive.append(r)
        else:
            negative.append(r)
    
    print("=" * 80)
    print(f"SUMMARY: {len(positive)} positive, {len(negative)} negative")
    print("=" * 80)
    
    if negative:
        print("\n✓ SQUARE REVERSAL FOUND:")
        for r in negative:
            pid, amt, pdate, method, sq_txn, sq_pay, pkey, notes = r
            print(f"  Payment {pid}: ${amt:,.2f} on {pdate} (Square: {sq_txn})")
    else:
        print("\n✗ NO REVERSAL FOUND - This is the issue!")
        print("  The Square reversal exists in Square but wasn't imported to PostgreSQL")
    
    # Check if there's a matching positive Square payment
    if positive:
        print("\nPOSITIVE $401.52 PAYMENTS:")
        for r in positive:
            pid, amt, pdate, method, sq_txn, sq_pay, pkey, notes = r
            if sq_txn or sq_pay:
                print(f"  Payment {pid}: Square payment on {pdate}")
            else:
                print(f"  Payment {pid}: Non-Square payment on {pdate} (method={method})")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
