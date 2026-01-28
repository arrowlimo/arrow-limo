#!/usr/bin/env python3
"""List all columns in vehicles table."""

import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REMOVED***'
)
cur = conn.cursor()

cur.execute("""
    SELECT column_name, data_type, character_maximum_length
    FROM information_schema.columns 
    WHERE table_name = 'vehicles'
    ORDER BY ordinal_position
""")

print("\nAll columns in vehicles table:\n")
print(f"{'Column Name':<40} {'Type':<20} {'Max Length'}")
print("-" * 80)
for row in cur.fetchall():
    col, dtype, maxlen = row
    print(f"{col:<40} {dtype:<20} {maxlen or ''}")

cur.close()
conn.close()
