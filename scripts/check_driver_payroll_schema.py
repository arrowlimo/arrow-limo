#!/usr/bin/env python3
import os, psycopg2

conn = psycopg2.connect(
    host='localhost', 
    database='almsdata', 
    user='postgres', 
    password='***REMOVED***'
)
cur = conn.cursor()

cur.execute("""
    SELECT column_name, data_type 
    FROM information_schema.columns 
    WHERE table_name = 'driver_payroll' 
    ORDER BY ordinal_position
""")

print("DRIVER_PAYROLL COLUMNS:")
for row in cur.fetchall():
    print(f"  {row[0]:<30} {row[1]}")

cur.close()
conn.close()
