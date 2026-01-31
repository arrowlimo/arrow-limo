import psycopg2
import os
import json

DB_HOST = os.environ.get('DB_HOST', 'localhost')
DB_NAME = os.environ.get('DB_NAME', 'almsdata')
DB_USER = os.environ.get('DB_USER', 'postgres')
DB_PASSWORD = os.environ.get('DB_PASSWORD', os.environ.get("DB_PASSWORD"))

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

cur.execute("""
    SELECT column_name, data_type
    FROM information_schema.columns
    WHERE table_name = 'receipts'
    ORDER BY ordinal_position
""")

cols = cur.fetchall()
print("Receipt table columns:")
for col_name, data_type in cols:
    print(f"  {col_name:40s} | {data_type}")

# Check for relevant columns
relevant = ['employee_id', 'reimbursed_via', 'reimbursement_date', 'reserve_number', 'charter_id']
print("\nLooking for:")
for col_name, data_type in cols:
    if any(keyword in col_name.lower() for keyword in ['employee', 'driver', 'reimburs', 'charter', 'reserve']):
        print(f"  ✓ Found: {col_name} ({data_type})")

conn.close()
