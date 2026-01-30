#!/usr/bin/env python3
"""
Clean up duplicate $195 payments for Reserve 012219.
LMS shows only ONE $195 Visa payment on 02/20/2016.
PostgreSQL has TWO $195 payments (26694 on 02/18, 26687 on 02/19).
Payment 26687 appears to be the real one (closer to LMS date).
Payment 26694 should be deleted as duplicate.
"""

import psycopg2
import os
import argparse
from datetime import datetime
from table_protection import create_backup_before_delete, log_deletion_audit

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REDACTED***')
    )

def main():
    parser = argparse.ArgumentParser(description='Clean up duplicate $195 payment for Reserve 012219')
    parser.add_argument('--write', action='store_true', 
                       help='Actually delete duplicate (default is dry-run)')
    args = parser.parse_args()
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("=" * 80)
    print("RESERVE 012219 - DUPLICATE $195 PAYMENT CLEANUP")
    print("=" * 80)
    print(f"Mode: {'WRITE' if args.write else 'DRY-RUN'}")
    print()
    
    # Show the duplicate $195 payments
    cur.execute("""
        SELECT 
            payment_id,
            amount,
            payment_date,
            payment_method,
            square_transaction_id,
            notes
        FROM payments 
        WHERE reserve_number = '012219' 
        AND amount = 195.00
        ORDER BY payment_date, payment_id
    """)
    
    rows = cur.fetchall()
    print(f"$195 payments found: {len(rows)}")
    print()
    
    for r in rows:
        pid, amt, pdate, method, sq_txn, notes = r
        print(f"Payment {pid}: ${amt:,.2f} on {pdate}")
        print(f"  Method: {method}")
        print(f"  Square TXN: {sq_txn}")
        print(f"  Notes: {notes}")
        print()
    
    print("=" * 80)
    print("LMS shows ONE $195 Visa payment on 02/20/2016")
    print("PostgreSQL has TWO $195 payments:")
    print("  - Payment 26694: 2016-02-18 (2 days early)")
    print("  - Payment 26687: 2016-02-19 (1 day early)")
    print()
    print("Recommendation: Delete 26694 as duplicate (further from LMS date)")
    print("=" * 80)
    print()
    
    if args.write:
        # Create backup first
        backup_name = create_backup_before_delete(
            cur, 
            'payments', 
            condition="payment_id = 26694"
        )
        print(f"✓ Created backup: {backup_name}")
        print()
        
        # Delete foreign key references first
        cur.execute("DELETE FROM income_ledger WHERE payment_id = 26694")
        fk_deleted = cur.rowcount
        if fk_deleted > 0:
            print(f"✓ Deleted {fk_deleted} income_ledger reference(s)")
        
        # Delete the duplicate payment
        cur.execute("DELETE FROM payments WHERE payment_id = 26694")
        deleted = cur.rowcount
        print(f"✓ Deleted {deleted} duplicate payment (ID 26694)")
        print()
        
        # Update charter balance
        cur.execute("""
            UPDATE charters 
            SET paid_amount = paid_amount - 195.00,
                balance = balance + 195.00,
                updated_at = %s
            WHERE reserve_number = '012219'
        """, (datetime.now(),))
        
        print("✓ Updated charter balance (-$195.00 paid)")
        print()
        
        # Log the deletion
        log_deletion_audit('payments', deleted, condition="payment_id = 26694 (duplicate $195 for Reserve 012219)")
        
        conn.commit()
        print("=" * 80)
        print("✓ CLEANUP APPLIED SUCCESSFULLY")
        print("=" * 80)
        
    else:
        print("=" * 80)
        print("DRY-RUN COMPLETE - Use --write to apply deletion")
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
                WHEN amount < 0 THEN 'REVERSAL'
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
        batch_info = f"batch={pkey}" if pkey else "no batch"
        print(f"  {pid}: ${amt:8,.2f} on {pdate} - {source} {status} ({batch_info})")
    
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
    
    print("\nExpected after cleanup:")
    print("  3 payments in batch: $195 + $401.52 + $200 = $796.52")
    print("  1 Square payment: $195 (26687)")
    print("  1 Square duplicate charge: $401.52 (26685)")
    print("  1 Square reversal: -$401.52 (53779)")
    print("  Total should be: $796.52 (matches total due)")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
