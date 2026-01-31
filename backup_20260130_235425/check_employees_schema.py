#!/usr/bin/env python3
"""Quick check of employees table schema."""

import os
import psycopg2

def get_db_connection():
    return psycopg2.connect(
        host=os.environ.get('DB_HOST', 'localhost'),
        database=os.environ.get('DB_NAME', 'almsdata'),
        user=os.environ.get('DB_USER', 'postgres'),
        password=os.environ.get('DB_PASSWORD')
    )

conn = get_db_connection()
cur = conn.cursor()

cur.execute("""
    SELECT column_name, data_type 
    FROM information_schema.columns 
    WHERE table_name = 'employees' 
    ORDER BY ordinal_position
""")

print("EMPLOYEES TABLE COLUMNS:")
for row in cur.fetchall():
    print(f"  {row[0]:<30} {row[1]}")

cur.close()
conn.close()
