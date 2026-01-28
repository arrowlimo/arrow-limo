#!/usr/bin/env python
"""
Rollback recent LMS charge inserts and placeholder charters created by sync scripts.
- Removes charter_charges with last_updated_by in ('lms_sync','lms_sync_specific')
- Removes placeholder charters for the known eight reserves
"""
import psycopg2
from datetime import datetime

DB_HOST = "localhost"
DB_NAME = "almsdata"
DB_USER = "postgres"
DB_PASSWORD = os.environ.get("DB_PASSWORD")

PLACEHOLDER_RESERVES = [
    '015901','015902','012861','016011','016021','016009','016010','016022'
]


def main():
    conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
    cur = conn.cursor()

    print("Starting rollback of LMS charge inserts and placeholders...")

    # Count charges before
    cur.execute("SELECT COUNT(*) FROM charter_charges")
    before_charges = cur.fetchone()[0]

    # Delete inserted charges by our scripts
    cur.execute("""
        DELETE FROM charter_charges
         WHERE last_updated_by IN ('lms_sync','lms_sync_specific')
    """)
    deleted_charges = cur.rowcount

    # Delete placeholder charters for specific reserves
    cur.execute("""
        DELETE FROM charters
         WHERE status = 'placeholder'
           AND reserve_number = ANY(%s)
    """, (PLACEHOLDER_RESERVES,))
    deleted_charters = cur.rowcount

    conn.commit()

    cur.execute("SELECT COUNT(*) FROM charter_charges")
    after_charges = cur.fetchone()[0]

    print(f"Deleted charges: {deleted_charges} | Charges before: {before_charges} -> after: {after_charges}")
    print(f"Deleted placeholder charters: {deleted_charters}")
    print("Rollback complete.")

    cur.close(); conn.close()

if __name__ == '__main__':
    main()
