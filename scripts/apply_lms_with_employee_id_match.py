#!/usr/bin/env python3
"""
Apply LMS driver data updates using employee_id as the join key.
This bypasses name verification for the 26 mismatched records.
"""
import os
import sys
import csv
import psycopg2
import psycopg2.extras

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

def main():
    # Read the mismatches CSV
    mismatches_file = r"L:\limo\reports\lms_driver_name_mismatches.csv"
    
    if not os.path.exists(mismatches_file):
        print(f"❌ File not found: {mismatches_file}")
        return
    
    updates = []
    with open(mismatches_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            updates.append({
                'employee_id': int(row['employee_id']),
                'employee_number': row['lms_code'],
                'name_note': f"DB: {row['db_name']}, LMS: {row['lms_name']}"
            })
    
    print(f"Found {len(updates)} employees to update")
    
    # Connect and update
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cur = conn.cursor()
    
    try:
        for u in updates:
            cur.execute("""
                UPDATE employees 
                SET employee_number = %s
                WHERE employee_id = %s
            """, (u['employee_number'], u['employee_id']))
            print(f"✅ Updated employee_id={u['employee_id']} → {u['employee_number']} ({u['name_note']})")
        
        conn.commit()
        print(f"\n✅ Committed {len(updates)} employee_number updates")
        
    except Exception as e:
        conn.rollback()
        print(f"❌ Rolled back: {e}")
        sys.exit(1)
    finally:
        cur.close()
        conn.close()

if __name__ == '__main__':
    main()
