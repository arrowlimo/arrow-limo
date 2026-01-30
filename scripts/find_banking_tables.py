#!/usr/bin/env python3
"""Find banking-related tables."""
import psycopg2

conn = psycopg2.connect(dbname='almsdata', user='postgres', password='***REDACTED***', host='localhost')
cur = conn.cursor()

cur.execute("""
    SELECT table_name 
    FROM information_schema.tables 
    WHERE table_schema='public' 
    AND (table_name LIKE '%bank%' OR table_name LIKE '%transaction%')
    ORDER BY table_name
""")

print("Banking-related tables:")
for row in cur.fetchall():
    print(f"  - {row[0]}")

conn.close()
