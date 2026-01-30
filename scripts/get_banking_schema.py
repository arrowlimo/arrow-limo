#!/usr/bin/env python3
import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()

cur.execute("""
    SELECT column_name, data_type 
    FROM information_schema.columns 
    WHERE table_name='banking_transactions' 
    ORDER BY ordinal_position
""")

print("BANKING_TRANSACTIONS SCHEMA:")
print("-" * 60)
for row in cur.fetchall():
    print(f"{row[0]:<40} {row[1]}")

cur.close()
conn.close()
