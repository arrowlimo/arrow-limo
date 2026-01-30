#!/usr/bin/env python3
import os, psycopg2

conn = psycopg2.connect(
    host='localhost', 
    database='almsdata', 
    user='postgres', 
    password='***REDACTED***'
)
cur = conn.cursor()

cur.execute("""
    SELECT column_name, data_type 
    FROM information_schema.columns 
    WHERE table_name = 'lms_staging_reserve' 
    ORDER BY ordinal_position
""")

print("LMS_STAGING_RESERVE COLUMNS:")
for row in cur.fetchall():
    print(f"  {row[0]:<30} {row[1]}")

cur.close()
conn.close()
