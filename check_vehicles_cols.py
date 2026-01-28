#!/usr/bin/env python3
import psycopg2
import os

conn = psycopg2.connect(
    host=os.environ.get("DB_HOST", "localhost"),
    database=os.environ.get("DB_NAME", "almsdata"),
    user=os.environ.get("DB_USER", "postgres"),
    password=os.environ.get("DB_PASSWORD", "***REMOVED***")
)
cur = conn.cursor()

# Get ACTUAL column names (not duplicates)
cur.execute("""
    SELECT DISTINCT column_name
    FROM information_schema.columns 
    WHERE table_name = 'vehicles'
    ORDER BY column_name
""")

print("=== ALL VEHICLES COLUMNS ===")
for col, in cur.fetchall():
    print(f"  {col}")

cur.close()
conn.close()
