#!/usr/bin/env python3
"""Check vehicle naming convention and structure."""

import psycopg2

DB_CONFIG = {
    'host': 'localhost',
    'database': 'almsdata',
    'user': 'postgres',
    'password': '***REDACTED***'
}

conn = psycopg2.connect(**DB_CONFIG)
cur = conn.cursor()

print("=" * 100)
print("CURRENT VEHICLE DATA")
print("=" * 100)

cur.execute("""
    SELECT vehicle_id, vehicle_name, license_plate, make, model, year, status, vehicle_type
    FROM vehicles 
    ORDER BY vehicle_id
    LIMIT 20
""")

rows = cur.fetchall()
print(f"{'ID':<5} {'Name':<20} {'Plate':<15} {'Make':<12} {'Model':<15} {'Year':<6} {'Status':<10} {'Type'}")
print("-" * 100)

for r in rows:
    vid = r[0]
    name = r[1] or 'NULL'
    plate = r[2] or 'NULL'
    make = r[3] or ''
    model = r[4] or ''
    year = str(r[5]) if r[5] else ''
    status = r[6] or ''
    vtype = r[7] or ''
    print(f"{vid:<5} {name:<20} {plate:<15} {make:<12} {model:<15} {year:<6} {status:<10} {vtype}")

print("\n" + "=" * 100)
print("SUGGESTED L-NAMING CONVENTION")
print("=" * 100)
print("Current → Suggested")
print("-" * 40)

for r in rows:
    vid = r[0]
    current_name = r[1] or 'NULL'
    suggested = f"L-{vid}"
    print(f"{current_name:<20} → {suggested}")

cur.close()
conn.close()
