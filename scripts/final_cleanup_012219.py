#!/usr/bin/env python3
"""
Final cleanup for Reserve 012219 - remove remaining duplicate Square $195.
Payment 26687 ($195 on 2016-02-19) duplicates batch payment 13844.
The batch payments are the authoritative records.
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
    parser = argparse.ArgumentParser(description='Final cleanup for Reserve 012219 duplicate Square $195')
    parser.add_argument('--write', action='store_true', 
                       help='Actually delete duplicate (default is dry-run)')
    args = parser.parse_args()
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("=" * 80)
    print("RESERVE 012219 - FINAL DUPLICATE CLEANUP")
    print("=" * 80)
    print(f"Mode: {'WRITE' if args.write else 'DRY-RUN'}")
    print()
    
    print("Current state:")
    print("  Batch 0012980: $195 (13844) + $401.52 (13848) + $200 (13849) = $796.52")
    print("  Square standalone: $195 (26687) + $401.52 (26685) - $401.52 (53779 reversal)")
    print()
    print("Issue: Payment 26687 ($195) duplicates batch payment 13844 ($195)")
    print("Solution: Delete payment 26687 (Square import duplicate)")
    print("=" * 80)
    print()
    
    if args.write:
        # Create backup
        backup_name = create_backup_before_delete(
            cur, 
            'payments', 
            condition="payment_id = 26687"
        )
        print(f"✓ Created backup: {backup_name}")
        print()
        
        # Delete foreign key references
        cur.execute("DELETE FROM income_ledger WHERE payment_id = 26687")
        fk_deleted = cur.rowcount
        if fk_deleted > 0:
            print(f"✓ Deleted {fk_deleted} income_ledger reference(s)")
        
        # Delete the duplicate
        cur.execute("DELETE FROM payments WHERE payment_id = 26687")
        deleted = cur.rowcount
        print(f"✓ Deleted {deleted} duplicate payment (ID 26687)")
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
        log_deletion_audit('payments', deleted, 
                          condition="payment_id = 26687 (Square duplicate of batch payment 13844)")
        
        conn.commit()
        print("=" * 80)
        print("✓ FINAL CLEANUP APPLIED SUCCESSFULLY")
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
                WHEN payment_key IS NOT NULL THEN 'Batch'
                ELSE 'Other'
            END as source,
            payment_key
        FROM payments 
        WHERE reserve_number = '012219'
        ORDER BY payment_date, payment_id
    """)
    
    total = 0
    print("\n  Batch payments (payment_key=0012980):")
    for row in cur.fetchall():
        pid, amt, pdate, method, source, pkey = row
        if pkey == '0012980':
            total += amt
            print(f"    {pid}: ${amt:8,.2f} on {pdate} - {source}")
    
    print("\n  Square payments (no batch):")
    cur.execute("""
        SELECT 
            payment_id,
            amount,
            payment_date
        FROM payments 
        WHERE reserve_number = '012219'
        AND payment_key IS NULL
        ORDER BY payment_date, payment_id
    """)
    
    for row in cur.fetchall():
        pid, amt, pdate = row
        total += amt
        status = "REVERSAL" if amt < 0 else "PAYMENT"
        print(f"    {pid}: ${amt:8,.2f} on {pdate} - Square {status}")
    
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
    
    if abs(bal) < 0.01:
        print("\n✓ PERFECT! Balance is $0.00")
    else:
        print(f"\n⚠ Balance should be $0.00, currently ${bal:,.2f}")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
