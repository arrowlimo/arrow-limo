#!/usr/bin/env python3
"""Find amount column name"""

import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REMOVED***'
)

cur = conn.cursor()
cur.execute("""
    SELECT column_name 
    FROM information_schema.columns 
    WHERE table_name = 'receipts' 
      AND column_name LIKE '%amount%'
    ORDER BY column_name
""")

print("Amount columns in receipts:")
for row in cur.fetchall():
    print(f"  - {row[0]}")

cur.close()
conn.close()
