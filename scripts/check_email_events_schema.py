#!/usr/bin/env python3
"""Check email_financial_events table structure"""
import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()

# Get table columns
cur.execute("""
    SELECT column_name, data_type 
    FROM information_schema.columns 
    WHERE table_name = 'email_financial_events'
    ORDER BY ordinal_position
""")

print("\nemail_financial_events columns:")
print("-" * 50)
for col, dtype in cur.fetchall():
    print(f"  {col:<30} {dtype}")

# Sample data
cur.execute("""
    SELECT *
    FROM email_financial_events
    WHERE source LIKE '%etransfer%'
    LIMIT 2
""")

print("\nSample rows:")
cols = [desc[0] for desc in cur.description]
for row in cur.fetchall():
    print("\n" + "="*50)
    for col, val in zip(cols, row):
        print(f"  {col}: {val}")

cur.close()
conn.close()
