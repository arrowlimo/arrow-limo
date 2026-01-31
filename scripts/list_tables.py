#!/usr/bin/env python3
"""Check what tables exist in local database."""
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

# List all tables
cur.execute("""
    SELECT table_name FROM information_schema.tables 
    WHERE table_schema = 'public' 
    ORDER BY table_name
""")

print("Tables in almsdata:")
for row in cur.fetchall():
    print(f"  {row[0]}")

cur.close()
conn.close()
