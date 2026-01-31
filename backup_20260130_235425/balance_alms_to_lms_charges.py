#!/usr/bin/env python3
"""
Fix the 20 charge mismatches by updating ALMS to match LMS charge totals.
This writes down phantom receivables to avoid paying GST on money never received.
"""

import pyodbc
import psycopg2
import os
from decimal import Decimal

LMS_PATH = r'L:\limo\database_backups\lms2026.mdb'
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REDACTED***")

# The 20 mismatched reserves
MISMATCHES = [
    '016202', '017943', '017991', '019236', '019463', '019588', '019595',
    '019598', '019642', '019731', '019745', '019758', '019759', '019760',
    '019761', '019836', '019839', '019845', '019846', '019848'
]


def get_lms_charge_total(reserve_no, lms_conn):
    """Get total charges from LMS for a reserve."""
    cur = lms_conn.cursor()
    cur.execute("SELECT SUM(Amount) FROM Charge WHERE Reserve_No = ?", (reserve_no,))
    row = cur.fetchone()
    return Decimal(str(row[0])) if row and row[0] else Decimal('0')


def get_alms_charter_info(reserve_no, alms_conn):
    """Get charter info from ALMS."""
    cur = alms_conn.cursor()
    cur.execute("""
        SELECT total_amount_due, balance, deposit
        FROM charters
        WHERE reserve_number = %s
    """, (reserve_no,))
    row = cur.fetchone()
    if row:
        return {
            'total_amount_due': row[0] or Decimal('0'),
            'balance': row[1] or Decimal('0'),
            'deposit': row[2] or Decimal('0')
        }
    return None


def get_alms_paid_total(reserve_no, alms_conn):
    """Get total paid amount from payments table."""
    cur = alms_conn.cursor()
    cur.execute("""
        SELECT COALESCE(SUM(amount), 0) 
        FROM payments 
        WHERE reserve_number = %s
    """, (reserve_no,))
    return Decimal(str(cur.fetchone()[0]))


def update_charter_amounts(reserve_no, new_total, alms_conn, dry_run=True):
    """Update ALMS charter to match LMS charge total."""
    cur = alms_conn.cursor()
    
    # Get current paid amount
    paid_amount = get_alms_paid_total(reserve_no, alms_conn)
    
    # Calculate new balance
    new_balance = new_total - paid_amount
    
    if dry_run:
        print(f"  [DRY RUN] Would update:")
        print(f"    total_amount_due = ${new_total:.2f}")
        print(f"    balance = ${new_balance:.2f} (${new_total:.2f} - ${paid_amount:.2f})")
    else:
        cur.execute("""
            UPDATE charters 
            SET total_amount_due = %s,
                balance = %s
            WHERE reserve_number = %s
        """, (new_total, new_balance, reserve_no))
        print(f"  ✓ Updated: total=${new_total:.2f}, balance=${new_balance:.2f}")
    
    return new_total, new_balance, paid_amount


def main():
    import sys
    dry_run = '--write' not in sys.argv
    
    if dry_run:
        print("="*80)
        print("DRY RUN MODE - No changes will be made")
        print("Run with --write to apply changes")
        print("="*80)
    else:
        print("="*80)
        print("WRITE MODE - Changes will be applied to database")
        print("="*80)
    
    lms_conn = pyodbc.connect(f'Driver={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={LMS_PATH};')
    alms_conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
    
    total_writedown = Decimal('0')
    updates = []
    
    try:
        for reserve_no in MISMATCHES:
            print(f"\n{'='*80}")
            print(f"Reserve {reserve_no}")
            print(f"{'='*80}")
            
            # Get LMS charge total
            lms_total = get_lms_charge_total(reserve_no, lms_conn)
            print(f"LMS Charge Total: ${lms_total:.2f}")
            
            # Get ALMS current info
            alms_info = get_alms_charter_info(reserve_no, alms_conn)
            if not alms_info:
                print(f"  ⚠ Charter not found in ALMS")
                continue
            
            print(f"ALMS Current Total: ${alms_info['total_amount_due']:.2f}")
            
            difference = alms_info['total_amount_due'] - lms_total
            print(f"Difference (ALMS - LMS): ${difference:.2f}")
            
            if abs(difference) <= Decimal('0.01'):
                print(f"  ✓ Already matches (within 1 cent)")
                continue
            
            # Update
            new_total, new_balance, paid_amount = update_charter_amounts(
                reserve_no, lms_total, alms_conn, dry_run
            )
            
            if difference > 0:
                total_writedown += difference
                updates.append({
                    'reserve': reserve_no,
                    'old_total': alms_info['total_amount_due'],
                    'new_total': new_total,
                    'writedown': difference,
                    'paid': paid_amount
                })
        
        # Summary
        print(f"\n\n{'='*80}")
        print("SUMMARY")
        print(f"{'='*80}")
        print(f"Reserves processed: {len(MISMATCHES)}")
        print(f"Updates needed: {len(updates)}")
        print(f"Total write-down: ${total_writedown:.2f}")
        
        if updates:
            print(f"\nWrite-downs by reserve:")
            for u in updates:
                print(f"  {u['reserve']}: ${u['old_total']:>10.2f} → ${u['new_total']:>10.2f} "
                      f"(write-down: ${u['writedown']:>10.2f}, paid: ${u['paid']:.2f})")
        
        if not dry_run:
            alms_conn.commit()
            print(f"\n✓ Changes committed to database")
        else:
            print(f"\n[DRY RUN] No changes made. Run with --write to apply.")
        
    except Exception as e:
        if not dry_run:
            alms_conn.rollback()
            print(f"\n❌ Error: {e}")
            print("Changes rolled back")
        raise
    finally:
        lms_conn.close()
        alms_conn.close()


if __name__ == '__main__':
    main()
