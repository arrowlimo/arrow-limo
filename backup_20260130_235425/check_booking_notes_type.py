#!/usr/bin/env python3
import psycopg2
import os

conn = psycopg2.connect(
    host=os.getenv('DB_HOST', 'localhost'),
    database=os.getenv('DB_NAME', 'almsdata'),
    user=os.getenv('DB_USER', 'postgres'),
    password=os.getenv('DB_PASSWORD', '***REDACTED***')
)
cur = conn.cursor()
cur.execute("""
    SELECT data_type, character_maximum_length 
    FROM information_schema.columns 
    WHERE table_name = 'charters' AND column_name = 'booking_notes'
""")
result = cur.fetchone()
print(f"booking_notes type: {result[0]}, max length: {result[1]}")

# Also check if TEXT type
if result[0] == 'text':
    print("✓ Already TEXT type (unlimited length)")
else:
    print(f"[WARN] Current type is {result[0]} with limit {result[1]}")
    print("Changing to TEXT...")
    cur.execute("ALTER TABLE charters ALTER COLUMN booking_notes TYPE TEXT")
    conn.commit()
    print("✓ Changed to TEXT type")
