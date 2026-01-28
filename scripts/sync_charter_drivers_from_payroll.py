#!/usr/bin/env python3
"""
Sync charter assigned_driver_id with driver_payroll employee_id

The payroll shows who actually worked and got paid (CRA authoritative).
Calendar/charter may show who was scheduled, but payroll shows reality.

This updates charter.assigned_driver_id to match the driver who was paid.
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
        password='***REMOVED***'
    )

def create_backup(conn):
    """Create backup of charters table before modifications"""
    cur = conn.cursor()
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_table = f'charters_backup_{timestamp}'
    
    print(f"\n📦 Creating backup: {backup_table}")
    
    # Backup only charters with driver mismatches
    cur.execute(f"""
        CREATE TABLE {backup_table} AS
        SELECT c.*
        FROM charters c
        JOIN driver_payroll dp ON dp.charter_id::integer = c.charter_id
        WHERE (dp.payroll_class = 'WAGE' OR dp.payroll_class IS NULL)
        AND c.assigned_driver_id IS NOT NULL
        AND dp.employee_id IS NOT NULL
        AND c.assigned_driver_id != dp.employee_id
    """)
    
    count = cur.rowcount
    conn.commit()
    cur.close()
    
    print(f"   ✓ Backed up {count:,} charter records")
    return backup_table

def analyze_driver_mismatches(conn):
    """Analyze driver mismatches between charter and payroll"""
    
    print("=" * 80)
    print("CHARTER-PAYROLL DRIVER MISMATCH ANALYSIS")
    print("=" * 80)
    
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    # Get mismatch count
    cur.execute("""
        SELECT COUNT(*) as mismatch_count
        FROM charters c
        JOIN driver_payroll dp ON dp.charter_id::integer = c.charter_id
        WHERE (dp.payroll_class = 'WAGE' OR dp.payroll_class IS NULL)
        AND c.assigned_driver_id IS NOT NULL
        AND dp.employee_id IS NOT NULL
        AND c.assigned_driver_id != dp.employee_id
    """)
    
    result = cur.fetchone()
    mismatch_count = result['mismatch_count']
    
    print(f"\n📊 MISMATCH SUMMARY:")
    print(f"   Charters with driver mismatches: {mismatch_count:,}")
    
    # Get sample mismatches with names
    print(f"\n🔍 SAMPLE MISMATCHES (showing scheduled vs actual driver):")
    cur.execute("""
        SELECT c.charter_id, c.reserve_number, c.charter_date,
               e_charter.full_name as scheduled_driver,
               e_payroll.full_name as actual_driver,
               dp.gross_pay as amount_paid
        FROM charters c
        JOIN driver_payroll dp ON dp.charter_id::integer = c.charter_id
        LEFT JOIN employees e_charter ON e_charter.employee_id = c.assigned_driver_id
        LEFT JOIN employees e_payroll ON e_payroll.employee_id = dp.employee_id
        WHERE (dp.payroll_class = 'WAGE' OR dp.payroll_class IS NULL)
        AND c.assigned_driver_id IS NOT NULL
        AND dp.employee_id IS NOT NULL
        AND c.assigned_driver_id != dp.employee_id
        ORDER BY c.charter_date DESC
        LIMIT 15
    """)
    
    mismatches = cur.fetchall()
    for row in mismatches:
        print(f"\n   Charter {row['reserve_number']} ({row['charter_date']}):")
        print(f"      Scheduled: {row['scheduled_driver']}")
        print(f"      Actual paid: {row['actual_driver']} (${row['amount_paid']:.2f})")
    
    # Get common substitution patterns
    print(f"\n📈 COMMON SUBSTITUTION PATTERNS:")
    cur.execute("""
        SELECT 
            e_charter.full_name as scheduled_driver,
            e_payroll.full_name as actual_driver,
            COUNT(*) as occurrences,
            SUM(dp.gross_pay) as total_paid
        FROM charters c
        JOIN driver_payroll dp ON dp.charter_id::integer = c.charter_id
        LEFT JOIN employees e_charter ON e_charter.employee_id = c.assigned_driver_id
        LEFT JOIN employees e_payroll ON e_payroll.employee_id = dp.employee_id
        WHERE (dp.payroll_class = 'WAGE' OR dp.payroll_class IS NULL)
        AND c.assigned_driver_id IS NOT NULL
        AND dp.employee_id IS NOT NULL
        AND c.assigned_driver_id != dp.employee_id
        GROUP BY e_charter.full_name, e_payroll.full_name
        HAVING COUNT(*) > 5
        ORDER BY COUNT(*) DESC
        LIMIT 10
    """)
    
    patterns = cur.fetchall()
    for row in patterns:
        print(f"   {row['scheduled_driver']} → {row['actual_driver']}: {row['occurrences']} times (${row['total_paid']:.2f} total)")
    
    cur.close()
    return mismatch_count

def sync_driver_assignments(conn, dry_run=True):
    """Update charter.assigned_driver_id to match payroll.employee_id"""
    
    print("\n" + "=" * 80)
    print("SYNCING DRIVER ASSIGNMENTS FROM PAYROLL")
    print("=" * 80)
    
    cur = conn.cursor()
    
    if dry_run:
        print("\n🔍 DRY RUN MODE - No changes will be made")
    else:
        print("\n✍️ WRITE MODE - Updating charter records")
    
    # Get list of charters to update
    cur.execute("""
        SELECT c.charter_id, c.reserve_number, 
               c.assigned_driver_id as old_driver_id,
               dp.employee_id as new_driver_id
        FROM charters c
        JOIN driver_payroll dp ON dp.charter_id::integer = c.charter_id
        WHERE (dp.payroll_class = 'WAGE' OR dp.payroll_class IS NULL)
        AND c.assigned_driver_id IS NOT NULL
        AND dp.employee_id IS NOT NULL
        AND c.assigned_driver_id != dp.employee_id
    """)
    
    updates_needed = cur.fetchall()
    update_count = len(updates_needed)
    
    print(f"\n📝 Found {update_count:,} charters to update")
    
    if not dry_run and update_count > 0:
        # Create backup first
        backup_table = create_backup(conn)
        
        print(f"\n⚙️ Updating charter driver assignments...")
        
        # Update assigned_driver_id to match payroll
        cur.execute("""
            UPDATE charters c
            SET assigned_driver_id = dp.employee_id,
                notes = COALESCE(notes || E'\n', '') || 
                        'Driver assignment updated to match payroll (actual driver paid) on ' || 
                        CURRENT_DATE::text || '.'
            FROM driver_payroll dp
            WHERE dp.charter_id::integer = c.charter_id
            AND (dp.payroll_class = 'WAGE' OR dp.payroll_class IS NULL)
            AND c.assigned_driver_id IS NOT NULL
            AND dp.employee_id IS NOT NULL
            AND c.assigned_driver_id != dp.employee_id
        """)
        
        updated = cur.rowcount
        conn.commit()
        
        print(f"   ✓ Updated {updated:,} charter records")
        print(f"   ✓ Backup saved as: {backup_table}")
    
    cur.close()
    return update_count

def verify_sync(conn):
    """Verify that driver assignments now match payroll"""
    
    print("\n" + "=" * 80)
    print("VERIFICATION")
    print("=" * 80)
    
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    # Check for remaining mismatches
    cur.execute("""
        SELECT COUNT(*) as remaining_mismatches
        FROM charters c
        JOIN driver_payroll dp ON dp.charter_id::integer = c.charter_id
        WHERE (dp.payroll_class = 'WAGE' OR dp.payroll_class IS NULL)
        AND c.assigned_driver_id IS NOT NULL
        AND dp.employee_id IS NOT NULL
        AND c.assigned_driver_id != dp.employee_id
    """)
    
    result = cur.fetchone()
    remaining = result['remaining_mismatches']
    
    print(f"\n✓ Remaining driver mismatches: {remaining:,}")
    
    if remaining == 0:
        print("   🎉 All charter driver assignments now match payroll!")
    else:
        print("   [WARN] Some mismatches remain - review needed")
    
    cur.close()

def main():
    parser = argparse.ArgumentParser(
        description='Sync charter driver assignments with payroll data'
    )
    parser.add_argument('--write', action='store_true',
                       help='Apply updates (default is dry-run)')
    
    args = parser.parse_args()
    
    print("=" * 80)
    print("CHARTER DRIVER ASSIGNMENT SYNC FROM PAYROLL")
    print("=" * 80)
    print("\nThis script updates charter.assigned_driver_id to match the driver")
    print("who actually worked and was paid (from payroll records).")
    print("\nPayroll data is the CRA-authoritative source for who worked.")
    print("=" * 80)
    
    conn = get_db_connection()
    
    try:
        # Analyze current state
        mismatch_count = analyze_driver_mismatches(conn)
        
        if mismatch_count > 0:
            # Sync driver assignments
            sync_driver_assignments(conn, dry_run=not args.write)
            
            # Verify if write mode
            if args.write:
                verify_sync(conn)
            else:
                print("\n" + "=" * 80)
                print("🔍 DRY RUN COMPLETE")
                print("=" * 80)
                print(f"\nTo apply these updates, run:")
                print(f"  python {__file__} --write")
        else:
            print("\n✓ No driver mismatches found - all charters match payroll!")
        
    finally:
        conn.close()
    
    print("\n" + "=" * 80)
    print("✓ Script complete")
    print("=" * 80)

if __name__ == '__main__':
    main()
