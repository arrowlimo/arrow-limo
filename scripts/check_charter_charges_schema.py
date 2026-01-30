#!/usr/bin/env python3
"""Check charter_charges table schema."""

import psycopg2

def get_db_connection():
    return psycopg2.connect(
        host="localhost",
        database="almsdata",
        user="postgres",
        password="***REDACTED***"
    )

conn = get_db_connection()
cur = conn.cursor()

cur.execute("""
    SELECT column_name, data_type, character_maximum_length
    FROM information_schema.columns
    WHERE table_name = 'charter_charges'
    ORDER BY ordinal_position
""")

print("CHARTER_CHARGES TABLE SCHEMA:")
print("=" * 80)
for row in cur.fetchall():
    col_name, data_type, max_len = row
    if max_len:
        print(f"  {col_name}: {data_type}({max_len})")
    else:
        print(f"  {col_name}: {data_type}")

print()
print("Sample data:")
cur.execute("SELECT * FROM charter_charges LIMIT 3")
for row in cur.fetchall():
    print(f"  {row}")

cur.close()
conn.close()
