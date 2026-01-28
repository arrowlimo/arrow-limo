#!/usr/bin/env python3
"""Add gst_exempt column to receipts table"""
import psycopg2
from psycopg2 import extensions

conn = psycopg2.connect(
    host="localhost",
    database="almsdata",
    user="postgres",
    password="***REMOVED***"
)
cur = conn.cursor()

try:
    # Check if column already exists
    cur.execute("""
        SELECT EXISTS (
            SELECT 1
            FROM information_schema.columns
            WHERE table_name='receipts' AND column_name='gst_exempt'
        )
    """)
    
    if cur.fetchone()[0]:
        print("✓ gst_exempt column already exists")
    else:
        print("Adding gst_exempt column to receipts table...")
        cur.execute("""
            ALTER TABLE receipts
            ADD COLUMN gst_exempt BOOLEAN DEFAULT FALSE
        """)
        conn.commit()
        print("✓ Added gst_exempt column (defaults to FALSE)")
        
except Exception as e:
    conn.rollback()
    print(f"❌ Error: {e}")
finally:
    cur.close()
    conn.close()
