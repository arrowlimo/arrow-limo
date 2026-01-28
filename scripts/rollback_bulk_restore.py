#!/usr/bin/env python3
"""
Rollback bulk restore - remove duplicated charges inserted by bulk_restore_lms_charges.py
Deletes all charter_charges rows with last_updated_by='bulk_restore_lms'
"""

import psycopg2
import os

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

def main():
    conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
    cur = conn.cursor()
    
    # Check how many rows to delete
    cur.execute("SELECT COUNT(*) FROM charter_charges WHERE last_updated_by = %s", ('bulk_restore_lms',))
    count = cur.fetchone()[0]
    
    print(f"Found {count} rows to delete (last_updated_by='bulk_restore_lms')")
    
    if count > 0:
        # Delete
        cur.execute("DELETE FROM charter_charges WHERE last_updated_by = %s", ('bulk_restore_lms',))
        conn.commit()
        print(f"✓ Deleted {cur.rowcount} rows")
    else:
        print("Nothing to delete")
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
