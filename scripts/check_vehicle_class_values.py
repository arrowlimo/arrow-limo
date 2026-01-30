#!/usr/bin/env python3
"""Check current values in vehicle classification columns."""

import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REDACTED***'
)
cur = conn.cursor()

print("\nCurrent vehicle classification columns:\n")
cur.execute("""
    SELECT vehicle_number, passenger_capacity, 
           vehicle_type, vehicle_category, vehicle_class
    FROM vehicles
    WHERE passenger_capacity IS NOT NULL
    ORDER BY passenger_capacity, vehicle_number
    LIMIT 25
""")

print(f"{'Vehicle#':<10} {'Pax':<5} {'Type':<30} {'Category':<20} {'Class'}")
print("-" * 95)
for row in cur.fetchall():
    vnum, pax, vtype, vcat, vclass = row
    print(f"{vnum:<10} {pax:<5} {vtype or 'NULL':<30} {vcat or 'NULL':<20} {vclass or 'NULL'}")

print("\n\nAre vehicle_category and vehicle_class populated?")
cur.execute("SELECT COUNT(*) FROM vehicles WHERE vehicle_category IS NOT NULL")
cat_count = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM vehicles WHERE vehicle_class IS NOT NULL")
class_count = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM vehicles")
total = cur.fetchone()[0]

print(f"  vehicle_category populated: {cat_count}/{total}")
print(f"  vehicle_class populated: {class_count}/{total}")

if cat_count == 0 and class_count == 0:
    print("\n✅ Columns exist but are empty - we can populate them with your regulatory logic!")

cur.close()
conn.close()
