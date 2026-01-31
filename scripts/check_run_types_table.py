#!/usr/bin/env python3
"""Check charter_run_types and related tables."""
import psycopg2
from dotenv import load_dotenv
import os
import sys

load_dotenv()

host = "localhost"
db_name = os.getenv("LOCAL_DB_NAME", "almsdata")
db_user = os.getenv("LOCAL_DB_USER", "alms")
db_password = os.getenv("LOCAL_DB_PASSWORD") or os.getenv("DB_PASSWORD")

try:
    conn = psycopg2.connect(host=host, database=db_name, user=db_user, password=db_password)
except Exception as e:
    print(f"❌ Connection failed: {e}")
    sys.exit(1)

cur = conn.cursor()

# Check charter_run_types
cur.execute("""
    SELECT column_name, data_type 
    FROM information_schema.columns 
    WHERE table_name = 'charter_run_types'
    ORDER BY ordinal_position
""")

print("charter_run_types columns:")
for col, dtype in cur.fetchall():
    print(f"  {col}: {dtype}")

# Show sample data
print("\nSample run types:")
cur.execute("SELECT * FROM charter_run_types LIMIT 5")
cols = [desc[0] for desc in cur.description]
for row in cur.fetchall():
    print(f"  {dict(zip(cols, row))}")

cur.close()
conn.close()
