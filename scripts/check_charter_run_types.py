#!/usr/bin/env python3
"""Check charter_run_types columns."""
import psycopg2
from dotenv import load_dotenv
import os

load_dotenv()

host = "localhost"
db_name = os.getenv("LOCAL_DB_NAME", "almsdata")
db_user = os.getenv("LOCAL_DB_USER", "alms")
db_password = os.getenv("LOCAL_DB_PASSWORD") or os.getenv("DB_PASSWORD")

conn = psycopg2.connect(host=host, database=db_name, user=db_user, password=db_password)
cur = conn.cursor()

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
print("\nSample data:")
cur.execute("SELECT * FROM charter_run_types LIMIT 3")
cols = [desc[0] for desc in cur.description]
for row in cur.fetchall():
    print(f"  {dict(zip(cols, row))}")

cur.close()
conn.close()
