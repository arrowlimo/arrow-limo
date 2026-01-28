#!/usr/bin/env python3
"""Check if Paul Mansell or Matt Kapustinsky exist in employees."""
import psycopg2

conn = psycopg2.connect(dbname='almsdata', user='postgres', password='***REMOVED***', host='localhost')
cur = conn.cursor()

cur.execute("""
    SELECT employee_id, full_name, first_name, last_name, status, is_chauffeur
    FROM employees 
    WHERE LOWER(full_name) LIKE '%mansell%' 
       OR LOWER(full_name) LIKE '%kapust%'
       OR LOWER(last_name) = 'mansell'
       OR LOWER(last_name) = 'kapustinsky'
    ORDER BY full_name
""")

rows = cur.fetchall()
print(f"Found {len(rows)} employees matching 'Mansell' or 'Kapustinsky':")
print(f"{'ID':<6} {'Full Name':<40} {'First':<15} {'Last':<20} {'Status':<12} {'Chauffeur'}")
print("-" * 110)
for r in rows:
    print(f"{r[0]:<6} {r[1] or '':<40} {r[2] or '':<15} {r[3] or '':<20} {r[4] or '':<12} {r[5]}")

cur.close()
conn.close()
