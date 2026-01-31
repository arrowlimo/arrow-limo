#!/usr/bin/env python3
"""Check if run_type_default_charges table exists and has data."""
import psycopg2
from dotenv import load_dotenv
import os
import sys

# Load .env
load_dotenv()

# Use LOCAL database for desktop app
host = "localhost"  # ALWAYS use localhost for local desktop app
db_name = os.getenv("LOCAL_DB_NAME", "almsdata")
db_user = os.getenv("LOCAL_DB_USER", "alms")
db_password = os.getenv("LOCAL_DB_PASSWORD") or os.getenv("DB_PASSWORD")

print(f"Connecting to: {host}/{db_name} as {db_user}")

try:
    conn = psycopg2.connect(
        host=host,
        database=db_name,
        user=db_user,
        password=db_password
    )
except Exception as e:
    print(f"❌ Connection failed: {e}")
    sys.exit(1)

cur = conn.cursor()

# Check if table exists
cur.execute("""
    SELECT EXISTS (
        SELECT 1 FROM information_schema.tables 
        WHERE table_name = 'run_type_default_charges'
    )
""")
exists = cur.fetchone()[0]
print(f'run_type_default_charges table exists: {exists}')

if exists:
    cur.execute('SELECT COUNT(*) FROM run_type_default_charges')
    count = cur.fetchone()[0]
    print(f'Total rows: {count}')
    
    if count > 0:
        # Show first few rows
        cur.execute('''SELECT run_type_id, charge_description, charge_type, amount, calc_type FROM run_type_default_charges ORDER BY run_type_id LIMIT 10''')
        rows = cur.fetchall()
        for row in rows:
            print(f'  {row}')
else:
    print('❌ Table does not exist - charges table must be created')

cur.close()
conn.close()
