#!/usr/bin/env python3
import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()

# Get columns
cur.execute("""
    SELECT column_name 
    FROM information_schema.columns 
    WHERE table_name='general_ledger' 
    ORDER BY ordinal_position
""")
print("GENERAL_LEDGER COLUMNS:")
columns = [row[0] for row in cur.fetchall()]
print(", ".join(columns))

# Get 1615 data
print("\n\nFIRST 20 ROWS WITH 1615:")
cur.execute(f"""
    SELECT * FROM general_ledger
    WHERE account LIKE '%1615%'
    LIMIT 20
""")

for row in cur.fetchall():
    print(row)

cur.close()
conn.close()
