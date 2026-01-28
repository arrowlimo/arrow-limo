#!/usr/bin/env python3
"""
Apply the same theory from Reserve 012219 to ALL suspicious batches:
1. Find duplicate Square imports that also exist in batches
2. Record missing Square reversals for duplicate charges
3. Clean up duplicate payments to achieve correct balances

Theory from 012219:
- Dispatcher charged twice by mistake → Square reversed it
- Payments imported twice (batch + Square standalone)
- Batch payments are authoritative, Square duplicates should be removed
- Missing Square reversals should be recorded
"""

import psycopg2
import os
import argparse
from datetime import datetime, timedelta
from decimal import Decimal
from collections import defaultdict
from table_protection import create_backup_before_delete, log_deletion_audit

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***')
    )

def find_duplicate_square_payments(cur, reserve_number):
    """
    Find Square payments that duplicate batch payments.
    Returns list of (payment_id, amount, date, square_txn, batch_payment_id)
    """
    cur.execute("""
        WITH batch_payments AS (
            SELECT payment_id, amount, payment_date, reserve_number
            FROM payments
            WHERE reserve_number = %s
            AND payment_key IS NOT NULL
            AND amount > 0
        ),
        square_payments AS (
            SELECT payment_id, amount, payment_date, reserve_number,
                   square_transaction_id
            FROM payments
            WHERE reserve_number = %s
            AND payment_key IS NULL
            AND square_transaction_id IS NOT NULL
            AND amount > 0
        )
        SELECT 
            s.payment_id as square_payment_id,
            s.amount,
            s.payment_date as square_date,
            s.square_transaction_id,
            b.payment_id as batch_payment_id,
            b.payment_date as batch_date
        FROM square_payments s
        JOIN batch_payments b 
            ON s.amount = b.amount
            AND ABS(EXTRACT(EPOCH FROM (s.payment_date::timestamp - b.payment_date::timestamp))) < 259200  -- 3 days
        ORDER BY s.payment_date, s.payment_id
    """, (reserve_number, reserve_number))
    
    return cur.fetchall()

def find_missing_square_reversals(cur, reserve_number):
    """
    Find Square positive payments that should have reversals but don't.
    A reversal should exist if:
    1. There's a positive Square payment
    2. There's a matching batch payment with same amount (indicates duplicate charge)
    3. No negative payment exists for that Square transaction
    """
    cur.execute("""
        WITH positive_square AS (
            SELECT 
                payment_id,
                amount,
                payment_date,
                square_transaction_id,
                square_payment_id,
                square_card_brand,
                square_last4
            FROM payments
            WHERE reserve_number = %s
            AND payment_key IS NULL
            AND square_transaction_id IS NOT NULL
            AND amount > 0
        ),
        negative_square AS (
            SELECT square_transaction_id
            FROM payments
            WHERE reserve_number = %s
            AND amount < 0
            AND square_transaction_id IS NOT NULL
        ),
        batch_payments AS (
            SELECT amount, payment_date
            FROM payments
            WHERE reserve_number = %s
            AND payment_key IS NOT NULL
            AND amount > 0
        )
        SELECT DISTINCT
            ps.payment_id,
            ps.amount,
            ps.payment_date,
            ps.square_transaction_id,
            ps.square_payment_id,
            ps.square_card_brand,
            ps.square_last4
        FROM positive_square ps
        -- Has matching batch payment (indicates duplicate)
        JOIN batch_payments bp 
            ON ps.amount = bp.amount
            AND ABS(EXTRACT(EPOCH FROM (ps.payment_date::timestamp - bp.payment_date::timestamp))) < 259200
        -- No reversal exists
        LEFT JOIN negative_square ns 
            ON ps.square_transaction_id = ns.square_transaction_id
        WHERE ns.square_transaction_id IS NULL
        ORDER BY ps.payment_date, ps.payment_id
    """, (reserve_number, reserve_number, reserve_number))
    
    return cur.fetchall()

def get_reserve_summary(cur, reserve_number):
    """Get current payment summary for a reserve."""
    cur.execute("""
        SELECT 
            COUNT(*) as total_payments,
            SUM(CASE WHEN payment_key IS NOT NULL THEN amount ELSE 0 END) as batch_total,
            SUM(CASE WHEN payment_key IS NULL AND square_transaction_id IS NOT NULL THEN amount ELSE 0 END) as square_total,
            SUM(amount) as total_paid
        FROM payments
        WHERE reserve_number = %s
    """, (reserve_number,))
    
    return cur.fetchone()

def process_reserve(cur, reserve_number, args):
    """Process one reserve for duplicates and missing reversals."""
    
    print(f"\n{'=' * 80}")
    print(f"RESERVE {reserve_number}")
    print(f"{'=' * 80}")
    
    # Get current summary
    total_payments, batch_total, square_total, total_paid = get_reserve_summary(cur, reserve_number)
    
    print(f"Current state:")
    print(f"  Total payments: {total_payments}")
    print(f"  Batch total: ${batch_total:,.2f}")
    print(f"  Square total: ${square_total:,.2f}")
    print(f"  Total paid: ${total_paid:,.2f}")
    
    # Find duplicates
    duplicates = find_duplicate_square_payments(cur, reserve_number)
    if duplicates:
        print(f"\n✗ Found {len(duplicates)} duplicate Square payments:")
        for dup in duplicates:
            sq_id, amt, sq_date, sq_txn, batch_id, batch_date = dup
            print(f"  Square payment {sq_id}: ${amt:,.2f} on {sq_date}")
            print(f"    Duplicates batch payment {batch_id} on {batch_date}")
    
    # Find missing reversals
    missing_reversals = find_missing_square_reversals(cur, reserve_number)
    if missing_reversals:
        print(f"\n✗ Found {len(missing_reversals)} missing Square reversals:")
        for rev in missing_reversals:
            pid, amt, pdate, sq_txn, sq_pay, brand, last4 = rev
            print(f"  Payment {pid}: ${amt:,.2f} on {pdate} needs reversal")
    
    if not duplicates and not missing_reversals:
        print(f"\n✓ No issues found - reserve is clean")
        return 0
    
    # Apply fixes if --write
    changes_made = 0
    
    if args.write:
        print(f"\n{'=' * 80}")
        print(f"APPLYING FIXES...")
        print(f"{'=' * 80}")
        
        # Record missing reversals first
        for rev in missing_reversals:
            pid, amt, pdate, sq_txn, sq_pay, brand, last4 = rev
            
            # Get full payment details
            cur.execute("""
                SELECT charter_id, client_id, account_number
                FROM payments WHERE payment_id = %s
            """, (pid,))
            charter_id, client_id, acct = cur.fetchone()
            
            reversal_date = pdate + timedelta(days=1)
            
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
                reserve_number,
                charter_id,
                client_id,
                acct,
                -amt,
                reversal_date,
                'credit_card',
                sq_txn,
                sq_pay,
                brand,
                last4,
                'refunded',
                f'Square reversal - duplicate charge ${amt:,.2f} on {pdate}',
                datetime.now()
            ))
            
            new_id = cur.fetchone()[0]
            print(f"✓ Created reversal payment {new_id}: -${amt:,.2f}")
            changes_made += 1
        
        # Delete duplicate Square payments
        for dup in duplicates:
            sq_id, amt, sq_date, sq_txn, batch_id, batch_date = dup
            
            # Delete income_ledger references
            cur.execute("DELETE FROM income_ledger WHERE payment_id = %s", (sq_id,))
            
            # Delete the payment
            cur.execute("DELETE FROM payments WHERE payment_id = %s", (sq_id,))
            print(f"✓ Deleted duplicate payment {sq_id}: ${amt:,.2f}")
            changes_made += 1
        
        # Update charter balance
        total_adjustment = sum(dup[1] for dup in duplicates)  # Amount of deleted payments
        
        cur.execute("""
            UPDATE charters 
            SET paid_amount = paid_amount - %s,
                balance = balance + %s,
                updated_at = %s
            WHERE reserve_number = %s
        """, (total_adjustment, total_adjustment, datetime.now(), reserve_number))
        
        print(f"✓ Updated charter balance: -${total_adjustment:,.2f} paid")
        
    else:
        print(f"\n{'=' * 80}")
        print(f"DRY-RUN - Use --write to apply fixes")
        print(f"{'=' * 80}")
    
    return changes_made

def main():
    parser = argparse.ArgumentParser(
        description='Fix all Square duplicates and missing reversals using 012219 theory'
    )
    parser.add_argument('--write', action='store_true',
                       help='Actually apply fixes (default is dry-run)')
    parser.add_argument('--reserve', type=str,
                       help='Process single reserve number (default: all suspicious)')
    parser.add_argument('--limit', type=int, default=100,
                       help='Limit number of reserves to process (default: 100)')
    args = parser.parse_args()
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("=" * 80)
    print("SQUARE DUPLICATE & REVERSAL FIX - BATCH PROCESSOR")
    print("=" * 80)
    print(f"Mode: {'WRITE' if args.write else 'DRY-RUN'}")
    print(f"Theory: Same as Reserve 012219 fix")
    print()
    
    # Get list of reserves to process
    if args.reserve:
        reserves = [args.reserve]
        print(f"Processing single reserve: {args.reserve}")
    else:
        # Get reserves with Square payments that might have issues
        cur.execute("""
            SELECT DISTINCT p1.reserve_number
            FROM payments p1
            WHERE p1.square_transaction_id IS NOT NULL
            AND p1.payment_key IS NULL
            AND p1.amount > 0
            AND EXISTS (
                SELECT 1 FROM payments p2
                WHERE p2.reserve_number = p1.reserve_number
                AND p2.payment_key IS NOT NULL
                AND p2.amount = p1.amount
            )
            ORDER BY p1.reserve_number
            LIMIT %s
        """, (args.limit,))
        
        reserves = [row[0] for row in cur.fetchall()]
        print(f"Found {len(reserves)} reserves with potential Square duplicates")
    
    print()
    
    # Process each reserve
    total_changes = 0
    reserves_fixed = 0
    
    for reserve in reserves:
        try:
            changes = process_reserve(cur, reserve, args)
            if changes > 0:
                reserves_fixed += 1
                total_changes += changes
                
                if args.write:
                    conn.commit()
                    
        except Exception as e:
            print(f"\n✗ ERROR processing reserve {reserve}: {e}")
            if args.write:
                conn.rollback()
            continue
    
    print(f"\n{'=' * 80}")
    print(f"SUMMARY")
    print(f"{'=' * 80}")
    print(f"Reserves processed: {len(reserves)}")
    print(f"Reserves with changes: {reserves_fixed}")
    print(f"Total changes made: {total_changes}")
    
    if not args.write:
        print(f"\nDRY-RUN COMPLETE - Use --write to apply all fixes")
    else:
        print(f"\n✓ ALL FIXES APPLIED SUCCESSFULLY")
        log_deletion_audit('payments', total_changes, 
                          condition=f"Square duplicate cleanup for {reserves_fixed} reserves")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
