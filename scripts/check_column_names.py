#!/usr/bin/env python3
"""Check actual column names for the tables with errors."""

import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REMOVED***'
)
cur = conn.cursor()

print("\nColumns in charters table (looking for status):")
cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'charters' AND column_name LIKE '%status%' ORDER BY ordinal_position")
for row in cur.fetchall():
    print(f"  - {row[0]}")

print("\nColumns in driver_payroll table (looking for date):")
cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'driver_payroll' AND column_name LIKE '%date%' ORDER BY ordinal_position")
for row in cur.fetchall():
    print(f"  - {row[0]}")

print("\nColumns in clients table (looking for phone):")
cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'clients' AND column_name LIKE '%phone%' ORDER BY ordinal_position")
for row in cur.fetchall():
    print(f"  - {row[0]}")

cur.close()
conn.close()
