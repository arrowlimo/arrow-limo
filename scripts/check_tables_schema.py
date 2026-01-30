#!/usr/bin/env python3
"""Quick check of table schemas."""
import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()

print("=== BANKING_TRANSACTIONS COLUMNS ===\n")
cur.execute("""
    SELECT column_name, data_type 
    FROM information_schema.columns 
    WHERE table_name = 'banking_transactions' 
    ORDER BY ordinal_position
""")
for row in cur.fetchall():
    print(f"  {row[0]:<30} {row[1]}")

print("\n=== RECEIPTS COLUMNS ===\n")
cur.execute("""
    SELECT column_name, data_type 
    FROM information_schema.columns 
    WHERE table_name = 'receipts' 
    ORDER BY ordinal_position
""")
for row in cur.fetchall():
    print(f"  {row[0]:<30} {row[1]}")

cur.close()
conn.close()
