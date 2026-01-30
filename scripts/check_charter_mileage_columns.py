#!/usr/bin/env python
"""Check charter mileage data columns."""

import psycopg2
import os

conn = psycopg2.connect(
    host=os.getenv('DB_HOST', 'localhost'),
    dbname=os.getenv('DB_NAME', 'almsdata'),
    user=os.getenv('DB_USER', 'postgres'),
    password=os.getenv('DB_PASSWORD', '***REDACTED***')
)
cur = conn.cursor()

print("\nChecking charter columns...")
cur.execute("""
    SELECT column_name, data_type 
    FROM information_schema.columns 
    WHERE table_name = 'charters' 
    AND (column_name LIKE '%odometer%' OR column_name LIKE '%km%' OR column_name LIKE '%mile%')
    ORDER BY ordinal_position
""")
print("Mileage-related columns in charters:")
for col, dtype in cur.fetchall():
    print(f"  {col}: {dtype}")

print("\nChecking sample data...")
cur.execute("""
    SELECT COUNT(*) as total,
           COUNT(CASE WHEN odometer_start IS NOT NULL THEN 1 END) as has_start,
           COUNT(CASE WHEN odometer_end IS NOT NULL THEN 1 END) as has_end,
           COUNT(CASE WHEN total_kms IS NOT NULL THEN 1 END) as has_total,
           COUNT(CASE WHEN vehicle_id IS NOT NULL THEN 1 END) as has_vehicle
    FROM charters
""")
total, has_start, has_end, has_total, has_vehicle = cur.fetchone()
print(f"\nTotal charters: {total:,}")
print(f"Has odometer_start: {has_start:,}")
print(f"Has odometer_end: {has_end:,}")
print(f"Has total_kms: {has_total:,}")
print(f"Has vehicle_id: {has_vehicle:,}")

print("\nSample rows with mileage:")
cur.execute("""
    SELECT charter_id, vehicle_id, odometer_start, odometer_end, total_kms
    FROM charters
    WHERE odometer_start IS NOT NULL
    LIMIT 10
""")
for row in cur.fetchall():
    print(f"  {row}")

cur.close()
conn.close()
