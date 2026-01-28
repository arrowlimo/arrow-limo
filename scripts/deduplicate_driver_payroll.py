"""
Remove duplicate driver_payroll records from WCB report imports.

CRITICAL ISSUE: 1,510 duplicate payroll records found ($43.7K duplicate amount)
- 1,201 duplicate groups identified
- Most from payroll_wcb_report source (duplicated 6-10 times)
- Employee 9's 2010-2011 entries particularly affected

STRATEGY:
1. Keep records with non-NULL employee_id over NULL
2. Keep non-WCB source over payroll_wcb_report
3. Keep earliest ID in each duplicate group
4. Verify T4 totals after cleanup

Usage:
    python deduplicate_driver_payroll.py                    # Dry-run (preview)
    python deduplicate_driver_payroll.py --write            # Execute with backup
"""

import psycopg2
import argparse
from datetime import datetime
from decimal import Decimal

def get_db_connection():
    return psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REMOVED***'
    )

def create_backup(cur):
    """Create timestamped backup table before deletion"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_table = f'driver_payroll_backup_{timestamp}'
    
    print(f"\n📦 Creating backup: {backup_table}")
    cur.execute(f"""
        CREATE TABLE {backup_table} AS 
        SELECT * FROM driver_payroll
    """)
    
    cur.execute(f"SELECT COUNT(*) FROM {backup_table}")
    count = cur.fetchone()[0]
    print(f"✅ Backup created: {count} payroll records saved")
    
    return backup_table

def find_duplicates(cur, min_copies=2):
    """Find duplicate payroll records grouped by employee + date + amount"""
    print("\n🔍 Finding duplicate payroll groups...")
    
    cur.execute("""
        SELECT 
            employee_id,
            pay_date,
            gross_pay,
            COUNT(*) as copies,
            array_agg(id ORDER BY id) as ids,
            array_agg(COALESCE(source, 'unknown') ORDER BY id) as sources
        FROM driver_payroll
        GROUP BY employee_id, pay_date, gross_pay
        HAVING COUNT(*) >= %s
        ORDER BY COUNT(*) DESC, gross_pay DESC
    """, (min_copies,))
    
    duplicates = cur.fetchall()
    
    print(f"✅ Found {len(duplicates)} duplicate groups")
    
    if duplicates:
        total_dupes = sum(row[3] - 1 for row in duplicates)
        total_amount = sum((row[2] or 0) * (row[3] - 1) for row in duplicates)
        print(f"   {total_dupes} duplicate records to remove")
        print(f"   ${total_amount:,.2f} duplicate amount")
    
    return duplicates

def analyze_duplicates(cur, duplicates, verbose=True):
    """Analyze duplicate patterns and determine which to keep/delete"""
    print("\n📊 Analyzing duplicate patterns...")
    
    keep_ids = []
    delete_ids = []
    
    for row in duplicates:
        emp_id, date, amount, copies, ids, sources = row
        
        # Priority for keeping:
        # 1. Non-WCB source over payroll_wcb_report
        # 2. Non-NULL employee_id (if mixed)
        # 3. Earliest ID
        
        keep_id = None
        
        # Priority 1: Non-WCB source
        for i, id in enumerate(ids):
            if sources[i] != 'payroll_wcb_report':
                keep_id = id
                break
        
        # Priority 2: Earliest ID
        if not keep_id:
            keep_id = ids[0]
        
        keep_ids.append(keep_id)
        
        # All other IDs are duplicates
        for id in ids:
            if id != keep_id:
                delete_ids.append(id)
        
        if verbose and len(duplicates) <= 20:
            emp_display = f"Employee {emp_id}" if emp_id else "Employee NULL"
            print(f"\n{emp_display} | {date} | ${amount or 0:.2f} ({copies} copies)")
            print(f"   KEEP: ID {keep_id} (source: {sources[ids.index(keep_id)]})")
            print(f"   DELETE: {[id for id in ids if id != keep_id]}")
    
    print(f"\n✅ Analysis complete:")
    print(f"   Keep: {len(keep_ids)} payroll records (1 per group)")
    print(f"   Delete: {len(delete_ids)} duplicates")
    
    return keep_ids, delete_ids

def delete_duplicates(cur, delete_ids):
    """Delete duplicate payroll records"""
    print(f"\n🗑️  Deleting {len(delete_ids)} duplicate payroll records...")
    
    # Delete in batches of 1000
    batch_size = 1000
    deleted = 0
    
    for i in range(0, len(delete_ids), batch_size):
        batch = delete_ids[i:i+batch_size]
        cur.execute("""
            DELETE FROM driver_payroll
            WHERE id = ANY(%s)
        """, (batch,))
        deleted += cur.rowcount
    
    print(f"✅ Deleted {deleted} duplicate payroll records")
    return deleted

def verify_cleanup(cur):
    """Verify no duplicates remain"""
    print("\n✅ Verifying cleanup...")
    
    cur.execute("""
        SELECT COUNT(*) as groups
        FROM (
            SELECT employee_id, pay_date, gross_pay, COUNT(*) as copies
            FROM driver_payroll
            GROUP BY employee_id, pay_date, gross_pay
            HAVING COUNT(*) > 1
        ) remaining
    """)
    
    remaining = cur.fetchone()[0]
    
    if remaining == 0:
        print("✅ SUCCESS: No duplicate groups remain")
    else:
        print(f"⚠️  WARNING: {remaining} duplicate groups still exist")
    
    return remaining

def show_top_duplicates(duplicates, limit=20):
    """Display top duplicate groups for review"""
    print(f"\n📋 Top {min(limit, len(duplicates))} duplicate groups:")
    print("=" * 100)
    
    for i, row in enumerate(duplicates[:limit], 1):
        emp_id, date, amount, copies, ids, sources = row
        
        emp_display = f"Employee {emp_id}" if emp_id else "Employee NULL"
        print(f"\n{i}. {emp_display} | {date} | ${amount or 0:.2f} ({copies} copies)")
        print(f"   IDs: {ids[:10]}{'...' if len(ids) > 10 else ''}")
        
        # Show source breakdown
        wcb_count = sum(1 for src in sources if src == 'payroll_wcb_report')
        if wcb_count > 0:
            print(f"   WCB source: {wcb_count}/{copies}")

def main():
    parser = argparse.ArgumentParser(description='Remove duplicate driver payroll records')
    parser.add_argument('--write', action='store_true', 
                       help='Execute deletion (default is dry-run)')
    parser.add_argument('--min-copies', type=int, default=2,
                       help='Minimum number of copies to consider duplicate (default: 2)')
    parser.add_argument('--verbose', action='store_true',
                       help='Show detailed analysis of each duplicate group')
    
    args = parser.parse_args()
    
    print("=" * 100)
    print("DRIVER PAYROLL DEDUPLICATION")
    print("=" * 100)
    
    if not args.write:
        print("\n🔍 DRY-RUN MODE (use --write to execute)")
    else:
        print("\n⚠️  WRITE MODE - Will delete duplicates with backup")
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Step 1: Create backup if writing
        backup_table = None
        if args.write:
            backup_table = create_backup(cur)
            conn.commit()
        
        # Step 2: Find duplicates
        duplicates = find_duplicates(cur, args.min_copies)
        
        if not duplicates:
            print("\n✅ No duplicates found!")
            return
        
        # Step 3: Show top duplicates
        show_top_duplicates(duplicates)
        
        # Step 4: Analyze and determine keep/delete
        keep_ids, delete_ids = analyze_duplicates(cur, duplicates, verbose=args.verbose)
        
        if not args.write:
            print("\n" + "=" * 100)
            print("DRY-RUN SUMMARY")
            print("=" * 100)
            print(f"Would delete: {len(delete_ids)} duplicate payroll records")
            print(f"Would keep: {len(keep_ids)} records (1 per group)")
            print(f"\nTo execute: python {__file__} --write")
            return
        
        # Step 5: Delete duplicates
        deleted_count = delete_duplicates(cur, delete_ids)
        conn.commit()
        
        # Step 6: Verify cleanup
        remaining = verify_cleanup(cur)
        
        print("\n" + "=" * 100)
        print("CLEANUP COMPLETE")
        print("=" * 100)
        print(f"✅ Deleted: {deleted_count} duplicate payroll records")
        print(f"✅ Backup: {backup_table}")
        print(f"✅ Remaining duplicates: {remaining}")
        print("\n⚠️  IMPORTANT: Verify T4 totals after cleanup")
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        conn.rollback()
        raise
    
    finally:
        cur.close()
        conn.close()

if __name__ == '__main__':
    main()
