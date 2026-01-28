#!/usr/bin/env python
"""Check schema for tax system testing."""

import psycopg2

conn = psycopg2.connect(
    host="localhost",
    dbname="almsdata",
    user="postgres",
    password="***REMOVED***"
)

cur = conn.cursor()

# Check driver_payroll columns
cur.execute("""
    SELECT column_name 
    FROM information_schema.columns 
    WHERE table_name = 'driver_payroll' 
    ORDER BY ordinal_position
""")
print("driver_payroll columns:")
for row in cur.fetchall():
    print(f"  - {row[0]}")

print()

# Sample data from 2012
cur.execute("""
    SELECT * FROM driver_payroll 
    WHERE year = 2012 
    LIMIT 5
""")
print("Sample 2012 payroll rows:")
cols = [desc[0] for desc in cur.description]
print("  Columns:", cols)
for row in cur.fetchall():
    print(f"    {row}")

print()

# Check employees table
cur.execute("""
    SELECT column_name 
    FROM information_schema.columns 
    WHERE table_name = 'employees' 
    ORDER BY ordinal_position
""")
print("employees columns:")
for row in cur.fetchall():
    print(f"  - {row[0]}")

conn.close()
