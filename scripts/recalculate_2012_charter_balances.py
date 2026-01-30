#!/usr/bin/env python3
"""
Recalculate paid_amount and balance for 2012 charters using reserve_number aggregation.

CRITICAL: Uses reserve_number (business key) NOT charter_id for payment aggregation.

Fixes:
  1. paid_amount = SUM(payments.amount) WHERE reserve_number matches
  2. balance = total_amount_due - paid_amount
  
Safe: Dry-run by default; --write to apply changes; --backup creates timestamped backup.
"""

import os
import sys
import psycopg2
from datetime import date, datetime
from decimal import Decimal

YEAR = 2012

DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_NAME = os.getenv('DB_NAME', 'almsdata')
DB_USER = os.getenv('DB_USER', 'postgres')
DB_PASSWORD = os.getenv('DB_PASSWORD', '***REDACTED***')

DRY_RUN = '--write' not in sys.argv
CREATE_BACKUP = '--backup' in sys.argv

def get_conn():
    return psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)

def create_backup(cur):
    """Create timestamped backup of charters table."""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_table = f'charters_backup_{timestamp}'
    
    cur.execute(f"""
        CREATE TABLE {backup_table} AS 
        SELECT * FROM charters 
        WHERE charter_date >= %s AND charter_date < %s
    """, (date(YEAR,1,1), date(YEAR+1,1,1)))
    
    count = cur.rowcount
    print(f"\n[BACKUP] Created {backup_table} with {count} rows")
    return backup_table

def recalculate_balances(cur, dry_run=True):
    """Recalculate paid_amount and balance using reserve_number aggregation."""
    
    # Get current state before changes
    cur.execute("""
        SELECT 
            COUNT(*) as total_charters,
            COUNT(CASE WHEN paid_amount IS NOT NULL THEN 1 END) as has_paid_amount,
            SUM(COALESCE(paid_amount, 0)) as total_paid_before,
            SUM(COALESCE(balance, 0)) as total_balance_before
        FROM charters
        WHERE charter_date >= %s AND charter_date < %s
    """, (date(YEAR,1,1), date(YEAR+1,1,1)))
    
    before = cur.fetchone()
    print("\n" + "="*80)
    print(f"BEFORE RECALCULATION ({YEAR})")
    print("="*80)
    print(f"Total charters: {before[0]}")
    print(f"Charters with paid_amount: {before[1]}")
    print(f"Total paid_amount: ${before[2]:,.2f}")
    print(f"Total balance: ${before[3]:,.2f}")
    
    # Calculate correct paid amounts from payments table
    # CRITICAL: Group by reserve_number, not charter_id
    # NOTE: Uses ALL payments regardless of payment_date to handle cross-year refunds
    cur.execute("""
        WITH payment_sums AS (
            SELECT 
                reserve_number,
                ROUND(SUM(COALESCE(amount, 0))::numeric, 2) as actual_paid
            FROM payments
            WHERE reserve_number IS NOT NULL
            GROUP BY reserve_number
        )
        SELECT 
            c.reserve_number,
            c.total_amount_due,
            c.paid_amount as old_paid,
            COALESCE(ps.actual_paid, 0) as new_paid,
            c.balance as old_balance,
            c.total_amount_due - COALESCE(ps.actual_paid, 0) as new_balance
        FROM charters c
        LEFT JOIN payment_sums ps ON ps.reserve_number = c.reserve_number
        WHERE c.charter_date >= %s AND c.charter_date < %s
        AND (
            ABS(c.paid_amount - COALESCE(ps.actual_paid, 0)) > 0.01
            OR c.balance IS NULL
            OR ABS(c.balance - (c.total_amount_due - COALESCE(ps.actual_paid, 0))) > 0.01
        )
        ORDER BY ABS(c.paid_amount - COALESCE(ps.actual_paid, 0)) DESC
    """, (date(YEAR,1,1), date(YEAR+1,1,1)))
    
    changes = cur.fetchall()
    
    print("\n" + "="*80)
    print(f"CHANGES TO APPLY ({len(changes)} charters)")
    print("="*80)
    
    if len(changes) == 0:
        print("\n[OK] No changes needed - all balances already correct!")
        return
    
    # Show sample of changes
    print("\nSample changes (first 20):")
    print("-" * 80)
    for i, change in enumerate(changes[:20], 1):
        reserve, total_due, old_paid, new_paid, old_bal, new_bal = change
        paid_diff = new_paid - (old_paid or 0)
        bal_diff = new_bal - (old_bal or 0)
        print(f"{i:3d}. Rsv {reserve}")
        print(f"     Total Due: ${total_due:,.2f}")
        print(f"     Paid: ${old_paid:,.2f} -> ${new_paid:,.2f} (diff: ${paid_diff:+,.2f})")
        print(f"     Balance: ${old_bal:,.2f} -> ${new_bal:,.2f} (diff: ${bal_diff:+,.2f})")
    
    if len(changes) > 20:
        print(f"\n... and {len(changes)-20} more charters")
    
    # Calculate totals
    total_paid_change = sum(change[3] - (change[2] or 0) for change in changes)
    total_bal_change = sum((change[5] or 0) - (change[4] or 0) for change in changes)
    
    print("\n" + "="*80)
    print("SUMMARY OF CHANGES")
    print("="*80)
    print(f"Charters to update: {len(changes)}")
    print(f"Total paid_amount adjustment: ${total_paid_change:+,.2f}")
    print(f"Total balance adjustment: ${total_bal_change:+,.2f}")
    
    if dry_run:
        print("\n[DRY RUN] No changes applied to database.")
        print("Run with --write flag to apply changes.")
        print("Add --backup flag to create backup before applying.")
        return
    
    # Apply updates
    print("\n" + "="*80)
    print("APPLYING UPDATES...")
    print("="*80)
    
    updated = 0
    for change in changes:
        reserve, total_due, old_paid, new_paid, old_bal, new_bal = change
        
        cur.execute("""
            UPDATE charters
            SET paid_amount = %s,
                balance = %s
            WHERE reserve_number = %s
            AND charter_date >= %s AND charter_date < %s
        """, (new_paid, new_bal, reserve, date(YEAR,1,1), date(YEAR+1,1,1)))
        
        updated += cur.rowcount
    
    print(f"\n[SUCCESS] Updated {updated} charters")
    
    # Verify after update
    cur.execute("""
        SELECT 
            COUNT(*) as total_charters,
            SUM(COALESCE(paid_amount, 0)) as total_paid_after,
            SUM(COALESCE(balance, 0)) as total_balance_after
        FROM charters
        WHERE charter_date >= %s AND charter_date < %s
    """, (date(YEAR,1,1), date(YEAR+1,1,1)))
    
    after = cur.fetchone()
    
    print("\n" + "="*80)
    print(f"AFTER RECALCULATION ({YEAR})")
    print("="*80)
    print(f"Total charters: {after[0]}")
    print(f"Total paid_amount: ${after[1]:,.2f} (was ${before[2]:,.2f})")
    print(f"Total balance: ${after[2]:,.2f} (was ${before[3]:,.2f})")
    print(f"Paid amount change: ${after[1] - before[2]:+,.2f}")
    print(f"Balance change: ${after[2] - before[3]:+,.2f}")

def main():
    print("\n" + "="*80)
    print(f"RECALCULATE {YEAR} CHARTER BALANCES")
    print("="*80)
    print("\nUsing reserve_number (business key) for payment aggregation")
    print(f"Mode: {'DRY RUN' if DRY_RUN else 'WRITE'}")
    
    conn = get_conn()
    cur = conn.cursor()
    
    try:
        if not DRY_RUN and CREATE_BACKUP:
            create_backup(cur)
            conn.commit()
        
        recalculate_balances(cur, dry_run=DRY_RUN)
        
        if not DRY_RUN:
            conn.commit()
            print("\n[COMMITTED] All changes saved to database")
        
    except Exception as e:
        conn.rollback()
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
    finally:
        cur.close()
        conn.close()
    
    print("\n" + "="*80)

if __name__ == '__main__':
    main()
