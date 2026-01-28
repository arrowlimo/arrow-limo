#!/usr/bin/env python3
import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

cur.execute("""
    SELECT column_name, data_type
    FROM information_schema.columns
    WHERE table_name = 'receipts'
    AND (column_name LIKE '%created%' OR column_name LIKE '%source%' OR column_name LIKE '%qb%' OR column_name LIKE '%quickbook%')
    ORDER BY column_name
""")

print("Receipt source/creation columns:")
for col, dtype in cur.fetchall():
    print(f"  {col} ({dtype})")

cur.close()
conn.close()
