#!/usr/bin/env python3
"""
Fix payments incorrectly linked to cancelled charters by:
1. Unlinking payments from cancelled charters
2. Re-matching payments to active charters by reserve_number
3. Creating backup before changes
"""

import psycopg2
from psycopg2.extras import RealDictCursor
import argparse
from datetime import datetime

def get_db_connection():
    return psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REDACTED***'
    )

def create_backup(conn):
    """Create backup of payments table"""
    cur = conn.cursor()
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_table = f'payments_backup_{timestamp}'
    
    print(f"\n📦 Creating backup: {backup_table}")
    
    # Backup payments linked to cancelled charters
    cur.execute(f"""
        CREATE TABLE {backup_table} AS
        SELECT p.*
        FROM payments p
        JOIN charters c ON c.charter_id = p.charter_id
        WHERE c.cancelled = true
    """)
    
    count = cur.rowcount
    conn.commit()
    cur.close()
    
    print(f"   ✓ Backed up {count:,} payments from cancelled charters")
    return backup_table

def unlink_payments_from_cancelled(conn, dry_run=True):
    """Unlink payments from cancelled charters"""
    
    print("\n" + "=" * 80)
    print("STEP 1: UNLINK PAYMENTS FROM CANCELLED CHARTERS")
    print("=" * 80)
    
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    # Get payments linked to cancelled charters
    cur.execute("""
        SELECT p.payment_id, p.reserve_number, p.amount, p.charter_id,
               c.reserve_number as charter_reserve
        FROM payments p
        JOIN charters c ON c.charter_id = p.charter_id
        WHERE c.cancelled = true
    """)
    
    payments_to_unlink = cur.fetchall()
    
    print(f"\n📊 Found {len(payments_to_unlink)} payments linked to cancelled charters")
    
    if payments_to_unlink:
        total_amount = sum(p['amount'] for p in payments_to_unlink)
        print(f"   Total amount: ${total_amount:,.2f}")
        
        if not dry_run:
            # Unlink by setting charter_id to NULL
            cur.execute("""
                UPDATE payments p
                SET charter_id = NULL
                FROM charters c
                WHERE p.charter_id = c.charter_id
                AND c.cancelled = true
            """)
            
            unlinked = cur.rowcount
            conn.commit()
            
            print(f"\n   ✓ Unlinked {unlinked:,} payments from cancelled charters")
        else:
            print(f"\n   🔍 DRY RUN: Would unlink {len(payments_to_unlink):,} payments")
    
    cur.close()
    return len(payments_to_unlink)

def rematch_payments_by_reserve(conn, dry_run=True):
    """Re-match unlinked payments to active charters by reserve_number"""
    
    print("\n" + "=" * 80)
    print("STEP 2: RE-MATCH PAYMENTS TO ACTIVE CHARTERS")
    print("=" * 80)
    
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    # Find unlinked payments with reserve_number
    cur.execute("""
        SELECT p.payment_id, p.reserve_number, p.amount, p.payment_date
        FROM payments p
        WHERE p.reserve_number IS NULL
        AND p.reserve_number IS NOT NULL
        AND p.reserve_number ~ '^[0-9]{6}$'
    """)
    
    unlinked = cur.fetchall()
    
    print(f"\n📊 Found {len(unlinked)} unlinked payments with reserve numbers")
    
    if unlinked:
        # Try to match to active charters
        matched_count = 0
        matched_amount = 0
        
        for payment in unlinked:
            # Find active charter with matching reserve number
            cur.execute("""
                SELECT charter_id, reserve_number, charter_date, cancelled
                FROM charters
                WHERE reserve_number = %s
                AND cancelled = false
                LIMIT 1
            """, (payment['reserve_number'],))
            
            charter = cur.fetchone()
            
            if charter:
                matched_count += 1
                matched_amount += payment['amount']
                
                if not dry_run:
                    # Link payment to active charter
                    cur.execute("""
                        UPDATE payments
                        SET charter_id = %s
                        WHERE payment_id = %s
                    """, (charter['charter_id'], payment['payment_id']))
        
        if not dry_run and matched_count > 0:
            conn.commit()
            print(f"\n   ✓ Re-matched {matched_count:,} payments to active charters")
            print(f"   ✓ Total amount re-matched: ${matched_amount:,.2f}")
        else:
            print(f"\n   🔍 DRY RUN: Would re-match {matched_count:,} payments (${matched_amount:,.2f})")
    
    cur.close()
    return matched_count if unlinked else 0

def verify_results(conn):
    """Verify the fix results"""
    
    print("\n" + "=" * 80)
    print("VERIFICATION")
    print("=" * 80)
    
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    # Check payments still on cancelled charters
    cur.execute("""
        SELECT COUNT(*) as cnt, SUM(p.amount) as total
        FROM payments p
        JOIN charters c ON c.charter_id = p.charter_id
        WHERE c.cancelled = true
    """)
    
    remaining = cur.fetchone()
    
    print(f"\n📊 Payments still on cancelled charters: {remaining['cnt']:,} (${remaining['total'] or 0:,.2f})")
    
    if remaining['cnt'] == 0:
        print("   [OK] SUCCESS: No payments linked to cancelled charters!")
    else:
        print("   [WARN] Some payments still on cancelled charters - may need manual review")
    
    # Check orphaned payments
    cur.execute("""
        SELECT COUNT(*) as cnt, SUM(amount) as total
        FROM payments
        WHERE reserve_number IS NULL
        AND reserve_number IS NOT NULL
    """)
    
    orphaned = cur.fetchone()
    
    print(f"\n📊 Orphaned payments with reserve numbers: {orphaned['cnt']:,} (${orphaned['total'] or 0:,.2f})")
    
    if orphaned['cnt'] > 0:
        print("   → These may be for cancelled charters or data entry errors")
    
    # Check overall payment distribution
    cur.execute("""
        SELECT 
            COUNT(*) as total_payments,
            COUNT(charter_id) as linked,
            COUNT(*) - COUNT(charter_id) as unlinked,
            SUM(amount) as total_amount
        FROM payments
    """)
    
    summary = cur.fetchone()
    
    print(f"\n📊 OVERALL PAYMENT SUMMARY:")
    print(f"   Total payments: {summary['total_payments']:,}")
    print(f"   Linked to charters: {summary['linked']:,} ({summary['linked']/summary['total_payments']*100:.1f}%)")
    print(f"   Unlinked: {summary['unlinked']:,} ({summary['unlinked']/summary['total_payments']*100:.1f}%)")
    print(f"   Total amount: ${summary['total_amount']:,.2f}")
    
    cur.close()

def main():
    parser = argparse.ArgumentParser(
        description='Fix payment mismatches - unlink from cancelled, rematch to active'
    )
    parser.add_argument('--write', action='store_true',
                       help='Apply fixes (default is dry-run)')
    
    args = parser.parse_args()
    
    print("=" * 80)
    print("PAYMENT MISMATCH FIX - CANCELLED CHARTERS")
    print("=" * 80)
    print("\nThis script will:")
    print("1. Unlink payments from cancelled charters")
    print("2. Re-match payments to active charters by reserve_number")
    print("=" * 80)
    
    conn = get_db_connection()
    
    try:
        if args.write:
            # Create backup first
            backup_table = create_backup(conn)
            print(f"\n✓ Backup created: {backup_table}")
        
        # Step 1: Unlink from cancelled
        unlinked_count = unlink_payments_from_cancelled(conn, dry_run=not args.write)
        
        # Step 2: Re-match to active
        rematched_count = rematch_payments_by_reserve(conn, dry_run=not args.write)
        
        # Verify
        if args.write:
            verify_results(conn)
        else:
            print("\n" + "=" * 80)
            print("🔍 DRY RUN COMPLETE")
            print("=" * 80)
            print(f"\nWould unlink: {unlinked_count} payments")
            print(f"Would re-match: {rematched_count} payments")
            print(f"\nTo apply fixes, run:")
            print(f"  python {__file__} --write")
        
    finally:
        conn.close()
    
    print("\n" + "=" * 80)
    print("✓ Script complete")
    print("=" * 80)

if __name__ == '__main__':
    main()
