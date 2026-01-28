#!/usr/bin/env python
"""Check banking_transactions columns."""

import psycopg2
import os

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

cur.execute("""
    SELECT column_name FROM information_schema.columns 
    WHERE table_name = 'banking_transactions' 
    ORDER BY ordinal_position
""")
print("banking_transactions columns:")
for col in cur.fetchall():
    print(f"  - {col[0]}")

cur.close()
conn.close()
