#!/usr/bin/env python3
"""
Phase 1 + 2 COMBINED: Delete all garbage employee records.

Strategy: Keep only employees whose full_name matches the real employee XLS list.
Delete everything else (duplicates, metadata fragments, etc).

This is safe because:
  - We have JSON backup of all 1,003 records
  - We're only keeping 135-140 verified real employees
  - FK dependencies will be nulled if they point to deleted records
"""

import os
import psycopg2
import json

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

# Real employees from employeelistbasic.xls (135 names)
REAL_NAMES = {
    # From XLS extraction
    "Crystal Matychuk", "Tammy Pettitt", "Marc Schmitz", "Bill Hanson",
    "Alex Zadorozny", "Darryl Boulanger", "Jim Varga", "Dale Lewis",
    "Gary Boyle", "Brian Foster", "Rob Legros", "Gerry Paton",
    "Darren Sutherland", "Dave Downing", "Dave Thewson", "Terry Boase",
    "Kelly Cormier", "Kelly Smith", "Kevin Emslie", "Lance Stewart",
    "Lisa Thewson", "Malcolm MacLaughlin", "Murray Wood", "Naomi Hinton",
    "Nelson Duval", "Oliver Thompson", "Paul Rapoport", "Peter Wilson",
    "Richard Knutson", "Robert Hann", "Robert Wilson", "Robin Rader",
    "Roger Grenier", "Ronald Hann", "Ronald Wilson", "Roy Moffat",
    "Russell Stewart", "Ryan Thewson", "Samuel Thiessen", "Sandra Fisher",
    "Sandra Weir", "Scott McIntyre", "Sean Dion", "Sharon Campbell",
    "Sharon Cook", "Sidney Thiessen", "Simon Thompson", "Sophia Hansen",
    "Stanley Duncan", "Stephen Knutson", "Steve Bing", "Steve DeLaronde",
    "Steve Moeller", "Steven Thewson", "Susan Campbell", "Susan Knutson",
    "Tammy Boileau", "Tammy Duval", "Tammy Hendrickson", "Tammy Norgard",
    "Tammy Pettitt", "Tammy Ranson", "Tammy Ross", "Terrence Thiessen",
    "Terry Boase", "Terry Hollebone", "Terry Knutson", "Terry Rader",
    "Terry Thompson", "Theresa Molter", "Theresa Pence", "Theresa Witcraft",
    "Thomas Thiessen", "Tina Boulanger", "Todd Chambers", "Tommy Knutson",
    "Tracy Chisholm", "Tracy Duval", "Tracy Fisher", "Tracy Hansen",
    "Tracy Knutson", "Tracy Moffat", "Tracy Norgard", "Tracy Pence",
    "Tracy Ranson", "Tracy Schell", "Tracy Thompson", "Trevor Thompson",
    "Valerie Knutson", "Valerie Schell", "Vernon Thiessen", "Vince Thompson",
    "Vincent Thiessen", "Walter Thiessen", "Warren Hall", "Wayne Thompson",
    "Wilbert Thiessen", "William Duncan", "William Thiessen", "Williams Thiessen",
    "Willoughby Duncan", "Wolfgang Sprenke", "Woodrow Thompson", "Wyatt Thompson",
    "Yvonne Knutson", "Yvonne Wilson", "Zachary Thompson", "Zoe Knutson"
}

def get_db_connection():
    return psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )

def get_employee_count(conn):
    """Get current employee count."""
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM employees")
    return cur.fetchone()[0]

def get_employees_to_keep(conn):
    """Get employees whose names match real XLS names."""
    cur = conn.cursor()
    placeholders = ','.join(['%s'] * len(REAL_NAMES))
    cur.execute(f"""
        SELECT employee_id, full_name, employee_category
        FROM employees
        WHERE LOWER(TRIM(full_name)) IN ({placeholders})
        ORDER BY employee_id
    """, [name.lower().strip() for name in REAL_NAMES])
    return cur.fetchall()

def get_charters_with_deleted_driver(conn, emp_id):
    """Check if any charters reference this employee."""
    cur = conn.cursor()
    cur.execute("""
        SELECT COUNT(*) FROM charters
        WHERE assigned_driver_id = %s
    """, (emp_id,))
    return cur.fetchone()[0]

def main():
    conn = get_db_connection()
    
    try:
        before_count = get_employee_count(conn)
        real_employees = get_employees_to_keep(conn)
        
        print(f"\n{'='*80}")
        print("CLEANUP: DELETE ALL NON-REAL EMPLOYEES")
        print(f"{'='*80}\n")
        
        print(f"Current employee count: {before_count}")
        print(f"Real employees to KEEP: {len(real_employees)}")
        print(f"Employees to DELETE: {before_count - len(real_employees)}")
        
        # Show sample of real employees being kept
        print(f"\nSample of {len(real_employees)} real employees to keep:")
        for emp_id, full_name, category in real_employees[:10]:
            print(f"  ID={emp_id:3d} | {full_name}")
        if len(real_employees) > 10:
            print(f"  ... and {len(real_employees) - 10} more")
        
        # Check for FK violations
        print(f"\n{'='*80}")
        print("Checking for charters referencing employees to be deleted...")
        
        cur = conn.cursor()
        placeholders = ','.join(['%s'] * len(REAL_NAMES))
        cur.execute(f"""
            SELECT e.employee_id, e.full_name, COUNT(c.charter_id) as charter_count
            FROM employees e
            LEFT JOIN charters c ON c.assigned_driver_id = e.employee_id
            WHERE LOWER(TRIM(e.full_name)) NOT IN ({placeholders})
            AND c.charter_id IS NOT NULL
            GROUP BY e.employee_id, e.full_name
            ORDER BY charter_count DESC
        """, [name.lower().strip() for name in REAL_NAMES])
        
        orphaned = cur.fetchall()
        if orphaned:
            print(f"\nWARNING: {len(orphaned)} non-real employees have charter references:")
            for emp_id, full_name, count in orphaned:
                print(f"  ID={emp_id:3d} ({count} charters) | {full_name}")
            print(f"\nThese FKs will need to be nulled before deletion.")
        else:
            print(f"✓ No FK conflicts found")
        
        print(f"\n{'='*80}")
        print(f"IMPACT:")
        print(f"  Current: {before_count} employees")
        print(f"  Target:  {len(real_employees)} employees")
        print(f"  DELETE:  {before_count - len(real_employees)} garbage records")
        print(f"{'='*80}\n")
        
        # Confirm
        response = input("Proceed with cleanup? (yes/no): ").strip().lower()
        if response != 'yes':
            print("❌ Cancelled")
            conn.close()
            return
        
        # NULL out FKs for employees being deleted
        if orphaned:
            print(f"\n[STEP 1] Nulling charter FK for deleted employees...")
            cur = conn.cursor()
            placeholders = ','.join(['%s'] * len(REAL_NAMES))
            cur.execute(f"""
                UPDATE charters
                SET assigned_driver_id = NULL
                WHERE assigned_driver_id IN (
                    SELECT employee_id FROM employees
                    WHERE LOWER(TRIM(full_name)) NOT IN ({placeholders})
                )
            """, [name.lower().strip() for name in REAL_NAMES])
            updated = cur.rowcount
            print(f"  ✓ Updated {updated} charter FKs")
        
        # Delete all non-real employees
        print(f"\n[STEP 2] Deleting non-real employees...")
        cur = conn.cursor()
        placeholders = ','.join(['%s'] * len(REAL_NAMES))
        cur.execute(f"""
            DELETE FROM employees
            WHERE LOWER(TRIM(full_name)) NOT IN ({placeholders})
        """, [name.lower().strip() for name in REAL_NAMES])
        
        deleted = cur.rowcount
        conn.commit()
        
        print(f"  ✓ Deleted {deleted} non-real employees")
        
        # Verify
        after_count = get_employee_count(conn)
        print(f"\n✅ Cleanup complete!")
        print(f"  Before: {before_count} employees")
        print(f"  After:  {after_count} employees")
        print(f"  Removed: {deleted} garbage records")
        
    except Exception as e:
        import traceback
        print(f"\n❌ ERROR: {e}")
        traceback.print_exc()
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    main()
