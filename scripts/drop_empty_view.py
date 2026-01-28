#!/usr/bin/env python3
"""Drop qb_export_general_journal VIEW (empty)."""

import psycopg2

def get_db_connection():
    return psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REMOVED***'
    )

conn = get_db_connection()
cur = conn.cursor()

try:
    cur.execute("DROP VIEW IF EXISTS qb_export_general_journal")
    conn.commit()
    print("✓ Dropped empty VIEW: qb_export_general_journal")
except Exception as e:
    print(f"✗ Error: {e}")
    conn.rollback()
finally:
    cur.close()
    conn.close()
