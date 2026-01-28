#!/usr/bin/env python3
import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

# Check if customers table exists
cur.execute("SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'customers')")
customers_exists = cur.fetchone()[0]

# Check if clients table exists
cur.execute("SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'clients')")
clients_exists = cur.fetchone()[0]

# Get charters table columns
cur.execute("""
    SELECT column_name 
    FROM information_schema.columns 
    WHERE table_name = 'charters' 
    ORDER BY ordinal_position
""")
charter_columns = [row[0] for row in cur.fetchall()]

print("=" * 60)
print("TABLE VERIFICATION FOR BROKEN CODE FIX")
print("=" * 60)
print(f"customers table exists: {customers_exists}")
print(f"clients table exists: {clients_exists}")
print()
print("Charters table columns:")
for col in charter_columns[:25]:  # First 25 columns
    print(f"  - {col}")
print()

# Check what columns the broken INSERT is trying to use
broken_columns = ['customer_name', 'phone', 'email']
print("Broken INSERT tries to use:")
for col in broken_columns:
    exists = col in charter_columns
    print(f"  - {col}: {'✅ EXISTS' if exists else '❌ MISSING'}")

cur.close()
conn.close()
