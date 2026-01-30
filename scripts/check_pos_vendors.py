#!/usr/bin/env python3
import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()

cur.execute("""
    SELECT DISTINCT vendor_name, COUNT(*) 
    FROM receipts 
    WHERE (vendor_name ILIKE '%point%of%sale%' OR vendor_name ILIKE '%pointofsale%')
      AND vendor_name NOT ILIKE '%peavey%'
      AND vendor_name NOT ILIKE '%pack%post%'
    GROUP BY vendor_name 
    ORDER BY COUNT(*) DESC
""")

print("CURRENT POINT OF SALE VENDOR NAMES")
print("=" * 70)
for row in cur.fetchall():
    print(f"{row[1]:>5} | {row[0]}")

cur.close()
conn.close()
