#!/usr/bin/env python3
"""
Check charter_id format mismatch between charter_payments and charters.
"""

import psycopg2

DB_HOST = 'localhost'
DB_PORT = 5432
DB_NAME = 'almsdata'
DB_USER = 'postgres'
DB_PASSWORD = 'ArrowLimousine'

conn = psycopg2.connect(
    host=DB_HOST,
    port=DB_PORT,
    database=DB_NAME,
    user=DB_USER,
    password=DB_PASSWORD
)
cur = conn.cursor()

# Get a sample of charter_id values from payments
query = """
SELECT DISTINCT cp.charter_id
FROM charter_payments cp
WHERE EXTRACT(YEAR FROM cp.payment_date) = 2012
ORDER BY cp.charter_id
LIMIT 20;
"""

print("Sample charter_id from charter_payments (2012):")
cur.execute(query)
for (charter_id,) in cur.fetchall():
    print(f"  {repr(charter_id)} (length: {len(str(charter_id)) if charter_id else 'NULL'})")

# Check if any charter IDs from charter_payments exist in charters
query2 = """
SELECT 
    cp.charter_id as cp_charter_id,
    c.charter_id as c_charter_id,
    CASE WHEN c.charter_id IS NOT NULL THEN 'MATCHED' ELSE 'NOT FOUND' END as status
FROM (
    SELECT DISTINCT charter_id FROM charter_payments 
    WHERE EXTRACT(YEAR FROM payment_date) = 2012
) cp
LEFT JOIN charters c ON cp.charter_id::text = c.charter_id::text
ORDER BY status DESC, cp.charter_id
LIMIT 30;
"""

print("\nMatching attempt:")
cur.execute(query2)
for cp_id, c_id, status in cur.fetchall():
    print(f"  CP:{repr(cp_id)} -> C:{repr(c_id)} [{status}]")

# Check what's in charters table for similar IDs
query3 = """
SELECT charter_id, reserve_number, charter_date
FROM charters
WHERE charter_date BETWEEN '2012-01-01' AND '2012-01-31'
ORDER BY charter_id
LIMIT 10;
"""

print("\nSample charters from 2012-01:")
cur.execute(query3)
for charter_id, reserve, date in cur.fetchall():
    print(f"  Charter ID: {charter_id} (type: {type(charter_id).__name__}), Reserve: {reserve}, Date: {date}")

cur.close()
conn.close()
