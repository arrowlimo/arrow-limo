#!/usr/bin/env python3
"""Quick script to check column names in staging tables."""
import os
import psycopg2

conn = psycopg2.connect(
    host=os.getenv('DB_HOST', 'localhost'),
    database=os.getenv('DB_NAME', 'almsdata'),
    user=os.getenv('DB_USER', 'postgres'),
    password=os.getenv('DB_PASSWORD', '***REDACTED***')
)
cur = conn.cursor()

tables = [
    'qb_accounts_staging',
    'lms_staging_customer', 
    'lms_staging_vehicles',
    'lms_staging_payment',
    'lms_staging_reserve',
    'staging_employee_reference_data',
    'vehicles',
    'clients',
    'employees'
]

for table in tables:
    print(f"\n{table}:")
    cur.execute(f"""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name = '{table}' 
        ORDER BY ordinal_position
    """)
    for row in cur.fetchall():
        print(f"  {row[0]} ({row[1]})")

cur.close()
conn.close()
