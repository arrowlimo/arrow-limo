#!/usr/bin/env python3
import psycopg2

conn = psycopg2.connect(
    host='localhost', 
    database='almsdata', 
    user='postgres', 
    password='***REDACTED***'
)
cur = conn.cursor()

# Check vehicles table for CVIP columns
cur.execute("""
    SELECT column_name, data_type 
    FROM information_schema.columns 
    WHERE table_name='vehicles' 
    AND column_name ILIKE '%cvip%'
    ORDER BY column_name
""")

print("CVIP columns in vehicles table:")
for row in cur.fetchall():
    print(f"  {row[0]}: {row[1]}")

# Also check what columns vehicles table has
cur.execute("""
    SELECT column_name, data_type 
    FROM information_schema.columns 
    WHERE table_name='vehicles'
    ORDER BY column_name
""")

print("\nAll vehicles table columns:")
for row in cur.fetchall():
    print(f"  {row[0]}: {row[1]}")

cur.close()
conn.close()
