#!/usr/bin/env python3
import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

# Check invoices table
cur.execute("SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_name='invoices')")
exists = cur.fetchone()[0]

print(f"Invoices table exists: {exists}")

if exists:
    # Check if it has any data
    cur.execute("SELECT COUNT(*) FROM invoices")
    count = cur.fetchone()[0]
    print(f"Invoices records: {count}")
    
    # Check table structure
    cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='invoices' ORDER BY column_name")
    columns = [row[0] for row in cur.fetchall()]
    print(f"Columns: {', '.join(columns)}")
else:
    print("Table does not exist - need to create it")

# Check if API references it
cur.execute("SELECT table_name FROM information_schema.tables WHERE table_name LIKE '%invoice%'")
invoice_tables = [row[0] for row in cur.fetchall()]
print(f"\nAll invoice-related tables: {invoice_tables}")

cur.close()
conn.close()
