#!/usr/bin/env python3
import psycopg2

conn = psycopg2.connect(
    host="localhost",
    database="almsdata",
    user="postgres",
    password="***REDACTED***"
)

cur = conn.cursor()

# Check receipts columns
print("=== RECEIPTS TABLE COLUMNS ===")
cur.execute("""
    SELECT column_name 
    FROM information_schema.columns 
    WHERE table_name = 'receipts' 
    ORDER BY ordinal_position
""")
for row in cur.fetchall():
    print(f"  - {row[0]}")

print("\n=== EMPLOYEES TABLE STATUS ===")
cur.execute("SELECT COUNT(*) FROM employees WHERE status = 'active'")
print(f"Active employees: {cur.fetchone()[0]}")

cur.execute("SELECT COUNT(*) FROM employees")
print(f"Total employees: {cur.fetchone()[0]}")

# Check employees columns
print("\n=== EMPLOYEES TABLE COLUMNS ===")
cur.execute("""
    SELECT column_name 
    FROM information_schema.columns 
    WHERE table_name = 'employees' 
    ORDER BY ordinal_position
""")
for row in cur.fetchall():
    print(f"  - {row[0]}")

print("\n=== VEHICLES TABLE STATUS ===")
cur.execute("SELECT COUNT(*) FROM vehicles")
print(f"Total vehicles: {cur.fetchone()[0]}")

# Check vehicles columns
print("\n=== VEHICLES TABLE COLUMNS ===")
cur.execute("""
    SELECT column_name 
    FROM information_schema.columns 
    WHERE table_name = 'vehicles' 
    ORDER BY ordinal_position
""")
for row in cur.fetchall():
    print(f"  - {row[0]}")

cur.close()
conn.close()
