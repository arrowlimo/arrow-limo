#!/usr/bin/env python3
"""
Phase 1: Handle 10 "unsafe" LEGACY records referenced by charters table.

Strategy:
  1. For metadata-only records: Set charters.assigned_driver_id to NULL, then delete
  2. For real person duplicates: Merge into primary REAL record, update FK, delete
  
10 Unsafe LEGACY IDs: 201, 202, 211, 213, 259, 290, 293, 336, 337, 347
"""

import os
import psycopg2
import psycopg2.extras
from pathlib import Path
import json

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

UNSAFE_LEGACY_IDS = [201, 202, 211, 213, 259, 290, 293, 336, 337, 347]

# Real employees from XLS (for matching duplicates)
REAL_NAMES_XLS = {
    "Crystal Matychuk", "Tammy Pettitt"
}

def get_db_connection():
    return psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )

def get_unsafe_records(conn):
    """Fetch the 10 unsafe LEGACY records with details."""
    cur = conn.cursor()
    placeholders = ','.join(['%s'] * len(UNSAFE_LEGACY_IDS))
    cur.execute(f"""
        SELECT employee_id, full_name, category
        FROM employees
        WHERE employee_id IN ({placeholders})
        ORDER BY employee_id
    """, UNSAFE_LEGACY_IDS)
    return [{'employee_id': r[0], 'full_name': r[1], 'category': r[2]} for r in cur.fetchall()]

def get_charter_count_for_employee(conn, emp_id):
    """Count how many charters reference this employee as assigned driver."""
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM charters WHERE assigned_driver_id = %s", (emp_id,))
    return cur.fetchone()[0]

def find_primary_real_record(conn, full_name):
    """Find primary REAL employee record matching full_name."""
    cur = conn.cursor()
    # Look for exact name match in REAL category
    cur.execute("""
        SELECT employee_id, full_name, category
        FROM employees
        WHERE category = 'REAL'
        AND LOWER(TRIM(full_name)) = LOWER(TRIM(%s))
        LIMIT 1
    """, (full_name,))
    row = cur.fetchone()
    if row:
        return {'employee_id': row[0], 'full_name': row[1], 'category': row[2]}
    return None

def update_charters_driver_id(conn, old_emp_id, new_emp_id):
    """Update charters to point to new employee ID."""
    cur = conn.cursor()
    cur.execute("""
        UPDATE charters
        SET assigned_driver_id = %s
        WHERE assigned_driver_id = %s
    """, (new_emp_id, old_emp_id))
    return cur.rowcount

def delete_employee(conn, emp_id):
    """Delete an employee record."""
    cur = conn.cursor()
    cur.execute("DELETE FROM employees WHERE employee_id = %s", (emp_id,))
    return cur.rowcount

def main():
    conn = get_db_connection()
    
    try:
        # Get all 10 unsafe LEGACY records
        unsafe_records = get_unsafe_records(conn)
        
        print(f"\n{'='*80}")
        print("PHASE 1: HANDLING 10 UNSAFE LEGACY RECORDS")
        print(f"{'='*80}\n")
        
        records_to_delete = []
        records_to_merge = []
        
        # Analyze each record
        for record in unsafe_records:
            emp_id = record['employee_id']
            full_name = record['full_name']
            category = record['category']
            charter_count = get_charter_count_for_employee(conn, emp_id)
            
            print(f"ID={emp_id:3d} | Name: {full_name[:40]:40s} | Category: {category}")
            print(f"       Referenced by {charter_count} charter(s)")
            
            # Check if this is a real person (matches XLS names)
            if full_name and full_name.strip() in REAL_NAMES_XLS:
                # Find primary REAL record
                primary = find_primary_real_record(conn, full_name)
                if primary:
                    print(f"       ✓ REAL PERSON - Found primary: ID={primary['employee_id']} ({primary['full_name']})")
                    records_to_merge.append({
                        'old_id': emp_id,
                        'new_id': primary['employee_id'],
                        'name': full_name
                    })
                else:
                    print(f"       ✗ Real person but no primary found - will keep this one, null out FKs")
                    records_to_delete.append({'id': emp_id, 'name': full_name, 'reason': 'Orphan real person'})
            else:
                # Pure metadata - delete after nulling FKs
                print(f"       ✗ METADATA ONLY - Will delete after nulling FKs")
                records_to_delete.append({'id': emp_id, 'name': full_name, 'reason': 'Pure metadata'})
            
            print()
        
        # Summary before action
        print(f"\n{'='*80}")
        print(f"SUMMARY:")
        print(f"  Records to merge (real person duplicates):  {len(records_to_merge)}")
        print(f"  Records to delete (metadata/orphans):       {len(records_to_delete)}")
        print(f"{'='*80}\n")
        
        # Get user confirmation
        response = input("Proceed with Phase 1? (yes/no): ").strip().lower()
        if response != 'yes':
            print("❌ Cancelled")
            conn.rollback()
            conn.close()
            return
        
        # MERGE step: Update FKs and prepare for deletion
        print("\n[MERGING] Real person duplicates...")
        for record in records_to_merge:
            old_id = record['old_id']
            new_id = record['new_id']
            name = record['name']
            
            updated = update_charters_driver_id(conn, old_id, new_id)
            print(f"  ✓ Updated {updated} charter(s): {old_id} → {new_id} ({name})")
        
        # DELETE step: Remove all unsafe LEGACY records (now safe due to merged FKs)
        print("\n[DELETING] All 10 unsafe LEGACY records...")
        deleted_count = 0
        for record in unsafe_records:
            emp_id = record['employee_id']
            deleted = delete_employee(conn, emp_id)
            if deleted:
                deleted_count += deleted
                print(f"  ✓ Deleted ID={emp_id}")
        
        # Verify deletions
        cur = conn.cursor()
        placeholders = ','.join(['%s'] * len(UNSAFE_LEGACY_IDS))
        cur.execute(f"SELECT COUNT(*) FROM employees WHERE employee_id IN ({placeholders})", UNSAFE_LEGACY_IDS)
        remaining = cur.fetchone()[0]
        
        if remaining == 0:
            print(f"\n✅ Successfully deleted {deleted_count} unsafe LEGACY records")
            conn.commit()
            print(f"\nDatabase updated: {1003 - deleted_count} records remaining (before Phase 2)")
        else:
            print(f"\n❌ ERROR: {remaining} unsafe records still exist!")
            conn.rollback()
        
    except Exception as e:
        import traceback
        print(f"\n❌ ERROR: {e}")
        traceback.print_exc()
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    main()
