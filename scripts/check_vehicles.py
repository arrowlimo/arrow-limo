#!/usr/bin/env python
import psycopg2
import os

conn = psycopg2.connect(
    host=os.environ.get('DB_HOST', 'localhost'),
    database=os.environ.get('DB_NAME', 'almsdata'),
    user=os.environ.get('DB_USER', 'postgres'),
    password=os.environ.get('DB_PASSWORD', '***REMOVED***')
)
cur = conn.cursor()

# Check all vehicles
cur.execute("SELECT COUNT(*) FROM vehicles")
total = cur.fetchone()[0]
print(f"Total vehicles: {total}")

cur.execute("SELECT vehicle_type, status, COUNT(*) FROM vehicles GROUP BY vehicle_type, status ORDER BY vehicle_type")
print("\nVehicle types by status:")
for vtype, status, count in cur.fetchall():
    print(f"  {vtype}: {status} ({count})")

conn.close()
