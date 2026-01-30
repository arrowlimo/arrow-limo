#!/usr/bin/env python3
"""Quick schema check for gl_transactions_staging."""
import psycopg2
import os

conn = psycopg2.connect(
    host=os.getenv('DB_HOST', 'localhost'),
    database=os.getenv('DB_NAME', 'almsdata'),
    user=os.getenv('DB_USER', 'postgres'),
    password=os.getenv('DB_PASSWORD', '***REDACTED***')
)

cur = conn.cursor()
cur.execute("""
    SELECT column_name, data_type 
    FROM information_schema.columns 
    WHERE table_name = 'gl_transactions_staging'
    ORDER BY ordinal_position
""")

print("gl_transactions_staging columns:")
for col_name, col_type in cur.fetchall():
    print(f"  {col_name:30} {col_type}")

cur.close()
conn.close()
