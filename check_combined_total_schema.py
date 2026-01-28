#!/usr/bin/env python3
import psycopg2

conn = psycopg2.connect('host=localhost dbname=almsdata user=postgres password=***REMOVED***')
cur = conn.cursor()

# Check all columns in receipts table
cur.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_name='receipts' ORDER BY ordinal_position")
print("=== RECEIPTS TABLE SCHEMA ===")
for row in cur.fetchall():
    print(f"{row[0]:35} {row[1]}")

# Check if there are any split-related fields
cur.execute("""
    SELECT column_name FROM information_schema.columns 
    WHERE table_name='receipts' 
    AND (column_name ILIKE '%split%' OR column_name ILIKE '%combined%' OR column_name ILIKE '%group%')
""")
print("\n=== SPLIT-RELATED FIELDS IN RECEIPTS ===")
results = cur.fetchall()
if results:
    for row in results:
        print(f"  {row[0]}")
else:
    print("  (none found)")

# Check receipt_splits table structure
cur.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_name='receipt_splits' ORDER BY ordinal_position")
print("\n=== RECEIPT_SPLITS TABLE SCHEMA ===")
for row in cur.fetchall():
    print(f"{row[0]:35} {row[1]}")

cur.close()
conn.close()
