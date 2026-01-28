#!/usr/bin/env python3
import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

# Check columns in clients table
print("Columns in clients table (first 20):")
cur.execute("""
    SELECT column_name FROM information_schema.columns 
    WHERE table_name = 'clients'
    ORDER BY ordinal_position
    LIMIT 20
""")
for i, row in enumerate(cur.fetchall(), 1):
    print(f"  {i:2}: {row[0]}")

# Check columns in charters table
print("\nColumns in charters table (first 20):")
cur.execute("""
    SELECT column_name FROM information_schema.columns 
    WHERE table_name = 'charters'
    ORDER BY ordinal_position
    LIMIT 20
""")
for i, row in enumerate(cur.fetchall(), 1):
    print(f"  {i:2}: {row[0]}")

# Check for customers table
print("\nDoes customers table exist?")
cur.execute("""
    SELECT EXISTS(SELECT 1 FROM information_schema.tables 
    WHERE table_name = 'customers')
""")
print(f"  {cur.fetchone()[0]}")

cur.close()
conn.close()
