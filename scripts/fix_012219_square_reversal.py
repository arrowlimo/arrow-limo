#!/usr/bin/env python3
"""
Fix Reserve 012219 by recording the missing Square reversal.
The dispatcher charged $401.52 twice, and Square reversed the first charge.
The reversal exists in Square but wasn't imported to PostgreSQL.
"""

import psycopg2
import os
import argparse
from datetime import datetime, timedelta
from table_protection import create_backup_before_delete, log_deletion_audit

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***')
    )

def main():
    parser = argparse.ArgumentParser(description='Fix Reserve 012219 Square reversal')
    parser.add_argument('--write', action='store_true', 
                       help='Actually apply the fix (default is dry-run)')
    args = parser.parse_args()
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("=" * 80)
    print("RESERVE 012219 - SQUARE REVERSAL FIX")
    print("=" * 80)
    print(f"Mode: {'WRITE' if args.write else 'DRY-RUN'}")
    print()
    
    # Get the original Square payment details
    cur.execute("""
        SELECT 
            payment_id,
            amount,
            payment_date,
            reserve_number,
            charter_id,
            client_id,
            account_number,
            square_transaction_id,
            square_payment_id,
            square_card_brand,
            square_last4
        FROM payments 
        WHERE payment_id = 26685
    """)
    
    original = cur.fetchone()
    if not original:
        print("ERROR: Original payment 26685 not found!")
        cur.close()
        conn.close()
        return
    
    (pid, amt, pdate, reserve, charter_id, client_id, acct, 
     sq_txn, sq_pay, card_brand, last4) = original
    
    print(f"Original Square Payment (to be reversed):")
    print(f"  Payment ID: {pid}")
    print(f"  Amount: ${amt:,.2f}")
    print(f"  Date: {pdate}")
    print(f"  Reserve: {reserve}")
    print(f"  Square TXN: {sq_txn}")
    print(f"  Square PAY: {sq_pay}")
    print()
    
    # Calculate reversal date (typically same day or next day)
    reversal_date = pdate + timedelta(days=1)
    
    print(f"Creating reversal payment:")
    print(f"  Amount: ${-amt:,.2f}")
    print(f"  Date: {reversal_date}")
    print(f"  Method: credit_card (Square reversal)")
    print(f"  Notes: Square reversal - dispatcher charged $401.52 twice by mistake")
    print()
    
    if args.write:
        # Insert the reversal payment
        cur.execute("""
            INSERT INTO payments (
                reserve_number,
                charter_id,
                client_id,
                account_number,
                amount,
                payment_date,
                payment_method,
                square_transaction_id,
                square_payment_id,
                square_card_brand,
                square_last4,
                status,
                notes,
                created_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
            RETURNING payment_id
        """, (
            reserve,
            charter_id,
            client_id,
            acct,
            -amt,  # Negative amount for reversal
            reversal_date,
            'credit_card',
            sq_txn,  # Same Square transaction ID
            sq_pay,  # Same Square payment ID
            card_brand,
            last4,
            'refunded',
            'Square reversal - dispatcher charged $401.52 twice by mistake on 2016-02-20, reversed 2016-02-21',
            datetime.now()
        ))
        
        new_payment_id = cur.fetchone()[0]
        print(f"✓ Created reversal payment ID: {new_payment_id}")
        print()
        
        # Update charter balance
        cur.execute("""
            SELECT paid_amount, balance 
            FROM charters 
            WHERE reserve_number = %s
        """, (reserve,))
        
        old_paid, old_balance = cur.fetchone()
        new_paid = old_paid - amt
        
        cur.execute("""
            UPDATE charters 
            SET paid_amount = paid_amount - %s,
                balance = balance + %s,
                updated_at = %s
            WHERE reserve_number = %s
        """, (amt, amt, datetime.now(), reserve))
        
        print(f"✓ Updated charter {reserve}:")
        print(f"  Old paid_amount: ${old_paid:,.2f}")
        print(f"  New paid_amount: ${new_paid:,.2f}")
        print(f"  Balance adjustment: +${amt:,.2f}")
        print()
        
        conn.commit()
        print("=" * 80)
        print("✓ FIX APPLIED SUCCESSFULLY")
        print("=" * 80)
        
    else:
        print("=" * 80)
        print("DRY-RUN COMPLETE - Use --write to apply changes")
        print("=" * 80)
    
    # Show final state
    print("\nFinal payment summary for Reserve 012219:")
    cur.execute("""
        SELECT 
            payment_id,
            amount,
            payment_date,
            payment_method,
            CASE 
                WHEN square_transaction_id IS NOT NULL THEN 'Square'
                ELSE 'Non-Square'
            END as source,
            payment_key
        FROM payments 
        WHERE reserve_number = '012219'
        ORDER BY payment_date, payment_id
    """)
    
    total = 0
    for row in cur.fetchall():
        pid, amt, pdate, method, source, pkey = row
        total += amt
        status = "REVERSAL" if amt < 0 else "PAYMENT"
        print(f"  {pid}: ${amt:8,.2f} on {pdate} - {source} {status} (batch={pkey})")
    
    print(f"\n  Total payments: ${total:,.2f}")
    
    # Show charter balance
    cur.execute("""
        SELECT total_amount_due, paid_amount, balance 
        FROM charters 
        WHERE reserve_number = '012219'
    """)
    
    due, paid, bal = cur.fetchone()
    print(f"\nCharter 012219 balance:")
    print(f"  Total due: ${due:,.2f}")
    print(f"  Paid: ${paid:,.2f}")
    print(f"  Balance: ${bal:,.2f}")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
