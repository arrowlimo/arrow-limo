#!/usr/bin/env python3
"""
Phase 2: Delete all 789 "safe" LEGACY_METADATA records.

These records have NO foreign key references and are pure metadata junk
from QuickBooks migration (addresses, phone fragments, PDF captions, etc).

Safe to delete without affecting any business data.
"""

import os
import psycopg2
import psycopg2.extras

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

def get_db_connection():
    return psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )

def get_safe_legacy_records(conn):
    """Fetch all LEGACY_METADATA records with no FK references."""
    cur = conn.cursor(psycopg2.extras.DictCursor)
    cur.execute("""
        SELECT e.employee_id, e.full_name, e.category
        FROM employees e
        WHERE e.category = 'LEGACY_METADATA'
        AND NOT EXISTS (
            SELECT 1 FROM driver_payroll WHERE employee_id = e.employee_id
        )
        AND NOT EXISTS (
            SELECT 1 FROM charters WHERE assigned_driver_id = e.employee_id
        )
        ORDER BY e.employee_id
    """)
    return cur.fetchall()

def main():
    conn = get_db_connection()
    
    try:
        # Get all safe LEGACY records
        safe_records = get_safe_legacy_records(conn)
        
        print(f"\n{'='*80}")
        print("PHASE 2: DELETE SAFE LEGACY_METADATA RECORDS")
        print(f"{'='*80}\n")
        
        print(f"Found {len(safe_records)} safe LEGACY_METADATA records to delete")
        print(f"These have NO foreign key references and are pure metadata junk.\n")
        
        # Show sample of what we're deleting
        print("Sample records to delete:")
        for record in safe_records[:10]:
            emp_id = record['employee_id']
            full_name = record['full_name']
            if full_name:
                full_name = full_name[:50]
            print(f"  ID={emp_id:3d} | {full_name}")
        
        if len(safe_records) > 10:
            print(f"  ... and {len(safe_records) - 10} more")
        
        print(f"\n{'='*80}")
        print(f"IMPACT:")
        print(f"  Records BEFORE: ~1003")
        print(f"  Records TO DELETE: {len(safe_records)}")
        print(f"  Records AFTER: ~{1003 - len(safe_records)}")
        print(f"{'='*80}\n")
        
        # Confirm with user
        response = input("Proceed with Phase 2? (yes/no): ").strip().lower()
        if response != 'yes':
            print("❌ Cancelled")
            conn.close()
            return
        
        # Delete all safe LEGACY records in bulk
        print(f"\n[DELETING] {len(safe_records)} safe LEGACY_METADATA records...")
        cur = conn.cursor()
        cur.execute("""
            DELETE FROM employees
            WHERE category = 'LEGACY_METADATA'
            AND NOT EXISTS (
                SELECT 1 FROM driver_payroll WHERE employee_id = employees.employee_id
            )
            AND NOT EXISTS (
                SELECT 1 FROM charters WHERE assigned_driver_id = employees.employee_id
            )
        """)
        
        deleted_count = cur.rowcount
        conn.commit()
        
        print(f"✅ Successfully deleted {deleted_count} safe LEGACY_METADATA records")
        
        # Verify remaining counts
        cur.execute("SELECT COUNT(*) FROM employees WHERE category = 'LEGACY_METADATA'")
        remaining_legacy = cur.fetchone()[0]
        
        cur.execute("SELECT COUNT(*) FROM employees")
        total_remaining = cur.fetchone()[0]
        
        print(f"\nDatabase now has:")
        print(f"  Total employees: {total_remaining}")
        print(f"  LEGACY_METADATA remaining: {remaining_legacy}")
        print(f"\nReady for Phase 3: Dedup QBO imports and drop empty columns")
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    main()
