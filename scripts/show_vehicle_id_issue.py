#!/usr/bin/env python3
"""Show charters with vehicle text but missing vehicle_id."""

import psycopg2

# Connect
conn = psycopg2.connect(
    host='localhost',
    database='almsdata', 
    user='postgres',
    password='***REMOVED***'
)
cur = conn.cursor()

# Get count
cur.execute("""
    SELECT COUNT(*) 
    FROM charters 
    WHERE vehicle IS NOT NULL AND vehicle_id IS NULL
""")
count = cur.fetchone()[0]
print(f"\n{'='*80}")
print(f"VEHICLE_ID MATCHING ISSUE")
print(f"{'='*80}\n")
print(f"📊 Total charters with vehicle text but NULL vehicle_id: {count:,}\n")

# Show sample charters needing fix
cur.execute("""
    SELECT charter_id, reserve_number, vehicle, charter_date::date
    FROM charters 
    WHERE vehicle IS NOT NULL AND vehicle_id IS NULL
    ORDER BY charter_date DESC
    LIMIT 20
""")
print("Sample charters needing vehicle_id (most recent):\n")
print(f"{'Charter ID':<12} {'Reserve#':<15} {'Vehicle Text':<20} {'Date'}")
print("-" * 70)
for row in cur.fetchall():
    charter_id, reserve_num, vehicle, date = row
    print(f"{charter_id:<12} {reserve_num or 'N/A':<15} {vehicle:<20} {date or 'N/A'}")

# Show vehicles table to match against
cur.execute("""
    SELECT vehicle_id, vehicle_number, make, model, year
    FROM vehicles
    WHERE vehicle_number SIMILAR TO 'L[0-9]+'
    ORDER BY vehicle_number
    LIMIT 15
""")
print(f"\n\nVehicles table (what we need to match to):\n")
print(f"{'ID':<6} {'Number':<10} {'Make':<12} {'Model':<20} {'Year'}")
print("-" * 70)
for row in cur.fetchall():
    vid, vnum, make, model, year = row
    print(f"{vid:<6} {vnum:<10} {make or 'N/A':<12} {model or 'N/A':<20} {year or 'N/A'}")

print(f"\n{'='*80}")
print("PROBLEM:")
print("  - Charters have vehicle TEXT ('L10', 'L19', 'L20', etc.)")
print("  - But vehicle_id foreign key is NULL")
print("  - Need to match 'L10' → vehicle_id where vehicle_number = 'L10'")
print(f"{'='*80}\n")

cur.close()
conn.close()
