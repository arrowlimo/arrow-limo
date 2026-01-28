#!/usr/bin/env python3
"""
Add missing LMS-related columns to employees table.
"""
import os
import psycopg2

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

# Add columns for driver/chauffeur licenses and permits
columns = [
    ("driver_license_number", "VARCHAR(50)"),
    ("driver_license_expiry", "DATE"),
    ("chauffeur_permit_number", "VARCHAR(50)"),
    ("chauffeur_permit_expiry", "DATE"),
]

for col_name, col_type in columns:
    try:
        cur.execute(f"""
            ALTER TABLE employees 
            ADD COLUMN IF NOT EXISTS {col_name} {col_type}
        """)
        print(f"✅ Added column: {col_name} ({col_type})")
    except Exception as e:
        print(f"❌ Failed to add {col_name}: {e}")
        conn.rollback()

try:
    conn.commit()
    print(f"\n✅ Committed {len(columns)} column additions")
except Exception as e:
    conn.rollback()
    print(f"❌ Rolled back: {e}")
finally:
    cur.close()
    conn.close()
