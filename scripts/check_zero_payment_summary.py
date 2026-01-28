#!/usr/bin/env python3
"""Check contents of zero_payment_summary table."""

import os
import psycopg2

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

conn = psycopg2.connect(
    host=DB_HOST,
    database=DB_NAME,
    user=DB_USER,
    password=DB_PASSWORD
)
cur = conn.cursor()

# Get structure
cur.execute("""
    SELECT column_name, data_type 
    FROM information_schema.columns 
    WHERE table_name = 'zero_payment_summary'
    ORDER BY ordinal_position
""")

print("zero_payment_summary structure:")
print("-"*80)
for col in cur.fetchall():
    print(f"  {col[0]:<30} {col[1]}")

# Get contents
cur.execute("SELECT * FROM zero_payment_summary")
print("\nContents (1 row):")
print("-"*80)
row = cur.fetchone()
print(row)

# Get column names for better display
cur.execute("""
    SELECT column_name 
    FROM information_schema.columns 
    WHERE table_name = 'zero_payment_summary'
    ORDER BY ordinal_position
""")
col_names = [c[0] for c in cur.fetchall()]

cur.execute("SELECT * FROM zero_payment_summary")
row = cur.fetchone()

print("\nFormatted:")
print("-"*80)
for col_name, value in zip(col_names, row):
    print(f"  {col_name:<30} {value}")

cur.close()
conn.close()
