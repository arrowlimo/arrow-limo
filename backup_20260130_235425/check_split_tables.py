#!/usr/bin/env python3
import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()

# Check if receipt_splits exists
cur.execute("""
    SELECT table_name 
    FROM information_schema.tables 
    WHERE table_schema = 'public' 
    AND table_name LIKE '%split%'
""")

tables = cur.fetchall()
print("Tables with 'split' in name:")
for row in tables:
    print(f"  - {row[0]}")

if tables:
    # Get columns of first split table
    table_name = tables[0][0]
    print(f"\nColumns in '{table_name}':")
    cur.execute(f"""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name = '{table_name}'
        ORDER BY ordinal_position
    """)
    
    for col, dtype in cur.fetchall():
        print(f"  - {col:35} {dtype}")
else:
    print("  (no split tables found)")

conn.close()
