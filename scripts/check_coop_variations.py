#!/usr/bin/env python3
import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

cur.execute("""
    SELECT DISTINCT vendor_name, COUNT(*) as cnt 
    FROM receipts 
    WHERE vendor_name ILIKE '%co-op%' 
       OR vendor_name ILIKE '%coop%' 
       OR vendor_name ILIKE '%centra%' 
       OR vendor_name ILIKE '%cooperator%'
    GROUP BY vendor_name 
    ORDER BY cnt DESC
""")

print("COUNT | VENDOR NAME")
print("-" * 70)
for row in cur.fetchall():
    print(f"{row[1]:>5} | {row[0]}")

cur.close()
conn.close()
