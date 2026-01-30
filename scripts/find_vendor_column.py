#!/usr/bin/env python3
"""Find vendor column name"""

import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REDACTED***'
)

cur = conn.cursor()
cur.execute("""
    SELECT column_name 
    FROM information_schema.columns 
    WHERE table_name = 'receipts' 
      AND (column_name LIKE '%vendor%' OR column_name LIKE '%supplier%' OR column_name LIKE '%payee%')
    ORDER BY column_name
""")

print("Vendor-related columns in receipts:")
for row in cur.fetchall():
    print(f"  - {row[0]}")

cur.close()
conn.close()
