#!/usr/bin/env python3
import psycopg2

conn = psycopg2.connect(host='localhost', user='postgres', database='almsdata', password='***REMOVED***')
cur = conn.cursor()
cur.execute("""
    SELECT column_name FROM information_schema.columns 
    WHERE table_name = 'receipts' 
    ORDER BY ordinal_position
""")

print("Tax/Category related columns:")
for row in cur.fetchall():
    col = row[0]
    if any(x in col.lower() for x in ['tax', 'category', 'jurisdiction', 'reason', 'province']):
        print(f"  {col}")

cur.close()
conn.close()
