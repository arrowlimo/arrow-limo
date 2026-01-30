#!/usr/bin/env python3
import os
import psycopg2

DB = dict(
    host=os.getenv('DB_HOST', 'localhost'),
    database=os.getenv('DB_NAME', 'almsdata'),
    user=os.getenv('DB_USER', 'postgres'),
    password=os.getenv('DB_PASSWORD', '***REDACTED***'),
)

with psycopg2.connect(**DB) as conn:
    with conn.cursor() as cur:
        cur.execute("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'receipts' 
            ORDER BY ordinal_position
        """)
        print("receipts table columns:")
        for row in cur.fetchall():
            print(f"  {row[0]}: {row[1]}")
