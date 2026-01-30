#!/usr/bin/env python3
"""Check receipts table schema for GL columns."""

import psycopg2

conn = psycopg2.connect(
    host="localhost",
    database="almsdata",
    user="postgres",
    password="***REDACTED***"
)

cur = conn.cursor()
cur.execute("""
    SELECT column_name, data_type 
    FROM information_schema.columns 
    WHERE table_name = 'receipts' 
    AND column_name LIKE '%gl%'
    ORDER BY ordinal_position
""")

for col, dtype in cur.fetchall():
    print(f"{col}: {dtype}")

cur.close()
conn.close()
