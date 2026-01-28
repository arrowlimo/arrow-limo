#!/usr/bin/env python3
"""Get vehicles table schema"""
import psycopg2
import os

DSN = dict(
    host=os.environ.get("DB_HOST", "localhost"),
    database=os.environ.get("DB_NAME", "almsdata"),
    user=os.environ.get("DB_USER", "postgres"),
    password=os.environ.get("DB_PASSWORD", "***REMOVED***"),
)

conn = psycopg2.connect(**DSN)
cur = conn.cursor()
cur.execute("""
    SELECT column_name 
    FROM information_schema.columns 
    WHERE table_name='vehicles' 
    ORDER BY ordinal_position
""")
cols = [r[0] for r in cur.fetchall()]
print("Vehicles table columns:")
print(", ".join(cols))
cur.close()
conn.close()
