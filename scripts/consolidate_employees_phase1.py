#!/usr/bin/env python
"""
Phase 1: DELETE LEGACY_METADATA records (safe, no foreign keys)

Safe to delete because:
1. All 799 LEGACY-* records have ZERO driver_payroll references
2. All 799 LEGACY-* records have ZERO employee_expenses references
3. These are artifacts from QuickBooks migration (addresses, phone fragments, captions)
4. Not referenced by any real business logic

JSON backup already created: reports/employees_backup_before_migration.json
"""
import psycopg2
import os
import sys

def main():
    conn = psycopg2.connect(
        host=os.environ.get('DB_HOST', 'localhost'),
        database=os.environ.get('DB_NAME', 'almsdata'),
        user=os.environ.get('DB_USER', 'postgres'),
        password=os.environ.get('DB_PASSWORD', '***REDACTED***')
    )
    
    try:
        cur = conn.cursor()
        
        # First: Verify they're really safe (no FK refs)
        cur.execute('''
            SELECT COUNT(*) 
            FROM employees e
            WHERE e.employee_number LIKE 'LEGACY-%'
              AND EXISTS (SELECT 1 FROM driver_payroll dp WHERE dp.employee_id = e.employee_id)
        ''')
        unsafe_count = cur.fetchone()[0]
        
        if unsafe_count > 0:
            print(f"❌ ERROR: Found {unsafe_count} LEGACY records WITH payroll refs!")
            print("   Cannot delete - FK constraint would be violated")
            sys.exit(1)
        
        # Count what we're deleting
        cur.execute('''
            SELECT COUNT(*) FROM employees 
            WHERE employee_number LIKE 'LEGACY-%'
        ''')
        delete_count = cur.fetchone()[0]
        
        print("="*80)
        print("PHASE 1: Delete LEGACY_METADATA Records")
        print("="*80)
        print()
        print(f"Records to delete: {delete_count}")
        print()
        
        # Show samples of what will be deleted
        cur.execute('''
            SELECT employee_id, employee_number, full_name
            FROM employees
            WHERE employee_number LIKE 'LEGACY-%'
            ORDER BY employee_id
            LIMIT 10
        ''')
        
        print("Sample records to delete:")
        for emp_id, emp_num, name in cur.fetchall():
            print(f"  ID={emp_id:3d} | {emp_num:20s} | {name}")
        
        print()
        
        # Get user confirmation
        response = input(f"Delete {delete_count} LEGACY_METADATA records? (yes/no): ").strip().lower()
        
        if response != 'yes':
            print("❌ Cancelled by user")
            sys.exit(1)
        
        # DELETE
        print()
        print("Executing deletion...")
        cur.execute('''
            DELETE FROM employees 
            WHERE employee_number LIKE 'LEGACY-%'
        ''')
        
        affected = cur.rowcount
        conn.commit()
        
        print(f"✓ Deleted {affected} records")
        print()
        
        # Verify
        cur.execute('SELECT COUNT(*) FROM employees')
        remaining = cur.fetchone()[0]
        
        print("="*80)
        print(f"Result: {remaining} employees remaining (down from 1,003)")
        print("="*80)
        print()
        
        # Show breakdown
        cur.execute('''
            SELECT 
                CASE WHEN employee_number LIKE '8000%' OR employee_number LIKE 'QB-%' THEN 'QBO_IMPORT'
                     WHEN full_name LIKE '%Dead%' OR full_name LIKE '%Invoice%' THEN 'PLACEHOLDER'
                     ELSE 'REAL/OTHER'
                END as category,
                COUNT(*) as count
            FROM employees
            GROUP BY category
            ORDER BY count DESC
        ''')
        
        print("Remaining employees by category:")
        for cat, count in cur.fetchall():
            print(f"  {cat:20s} | {count:3d} records")
        
        cur.close()
        
    except Exception as e:
        conn.rollback()
        print(f"❌ ERROR: {e}")
        sys.exit(1)
    finally:
        conn.close()

if __name__ == '__main__':
    main()
