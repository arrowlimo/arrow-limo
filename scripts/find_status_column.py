#!/usr/bin/env python3
"""Find the status column name in charters table."""

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
    WHERE table_name = 'charters' 
      AND (column_name LIKE '%status%' OR column_name LIKE '%cancel%' OR column_name LIKE '%state%')
    ORDER BY column_name
""")

print("Status/Cancel/State columns in charters table:")
for row in cur.fetchall():
    print(f"  - {row[0]}")

cur.close()
conn.close()
