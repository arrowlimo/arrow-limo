#!/usr/bin/env python3
import psycopg2
import os

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

conn = psycopg2.connect(
    host=DB_HOST,
    database=DB_NAME,
    user=DB_USER,
    password=DB_PASSWORD
)
cur = conn.cursor()

# Get vehicles table schema
cur.execute("""
    SELECT column_name, data_type
    FROM information_schema.columns
    WHERE table_name='vehicles'
    ORDER BY ordinal_position
""")

print("\n=== VEHICLES TABLE SCHEMA ===")
for col, dtype in cur.fetchall():
    print(f"  {col}: {dtype}")

# Get sample data
print("\n=== SAMPLE DATA ===")
cur.execute("SELECT * FROM vehicles LIMIT 3")
cols = [desc[0] for desc in cur.description]
print("Columns:", ", ".join(cols))
for row in cur.fetchall():
    print(f"Row: {dict(zip(cols, row))}")

cur.close()
conn.close()
