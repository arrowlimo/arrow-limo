#!/usr/bin/env python
"""Check for duplicate vehicles after reclassification."""

import psycopg2
import os

conn = psycopg2.connect(
    host=os.getenv('DB_HOST', 'localhost'),
    dbname=os.getenv('DB_NAME', 'almsdata'),
    user=os.getenv('DB_USER', 'postgres'),
    password=os.getenv('DB_PASSWORD', '***REMOVED***')
)
cur = conn.cursor()

print("\n" + "=" * 120)
print("CHECKING FOR DUPLICATE VEHICLES")
print("=" * 120)

# Check for duplicates based on VIN, license plate, or make/model/year combination
cur.execute("""
    WITH vehicle_groups AS (
        SELECT 
            vehicle_id,
            unit_number,
            vehicle_type,
            make,
            model,
            year,
            vin_number,
            license_plate,
            passenger_capacity,
            CASE 
                WHEN vin_number IS NOT NULL AND vin_number != '' THEN vin_number
                WHEN license_plate IS NOT NULL AND license_plate != '' THEN license_plate
                ELSE CONCAT(COALESCE(make, ''), '-', COALESCE(model, ''), '-', COALESCE(year::text, ''))
            END as group_key
        FROM vehicles
        WHERE passenger_capacity >= 13
    )
    SELECT 
        v.*,
        COUNT(*) OVER (PARTITION BY group_key) as dup_count
    FROM vehicle_groups v
    ORDER BY dup_count DESC, vehicle_id
""")

rows = cur.fetchall()

print(f"\n{'ID':<6} {'Unit#':<8} {'Type':<30} {'Make/Model/Year':<35} {'VIN':<20} {'Plate':<12} {'Cap':<5} {'Dups':<5}")
print("-" * 120)

has_duplicates = False
duplicate_groups = {}

for vid, unit, vtype, make, model, year, vin, plate, cap, group_key, dup_count in rows:
    make_model = f"{make or ''} {model or ''} {year or ''}".strip()
    
    dup_marker = ""
    if dup_count > 1:
        has_duplicates = True
        dup_marker = f"⚠️  {dup_count}"
        if group_key not in duplicate_groups:
            duplicate_groups[group_key] = []
        duplicate_groups[group_key].append({
            'id': vid,
            'unit': unit,
            'type': vtype,
            'vehicle': make_model,
            'vin': vin,
            'plate': plate,
            'capacity': cap
        })
    else:
        dup_marker = "✅"
    
    print(f"{vid:<6} {unit or 'N/A':<8} {vtype or 'Unknown':<30} {make_model:<35} {vin or 'N/A':<20} {plate or 'N/A':<12} {cap or 'N/A':<5} {dup_marker:<5}")

print("\n" + "=" * 120)

if has_duplicates:
    print("⚠️  DUPLICATES DETECTED!")
    print("=" * 120)
    print("\nDuplicate Groups:")
    print("-" * 120)
    
    for group_key, vehicles in duplicate_groups.items():
        print(f"\nGroup Key: {group_key}")
        print(f"  Count: {len(vehicles)} vehicles")
        for v in vehicles:
            print(f"  - ID {v['id']}: {v['vehicle']} (VIN: {v['vin'] or 'N/A'}, Plate: {v['plate'] or 'N/A'})")
else:
    print("✅ NO DUPLICATES FOUND - Each vehicle is unique!")

print("=" * 120)

# Also check the entire vehicles table for any duplicates
print("\n" + "=" * 120)
print("FULL VEHICLE TABLE DUPLICATE CHECK")
print("=" * 120)

cur.execute("""
    SELECT 
        COUNT(*) as total_vehicles,
        COUNT(DISTINCT vehicle_id) as unique_ids,
        COUNT(DISTINCT vin_number) FILTER (WHERE vin_number IS NOT NULL AND vin_number != '') as unique_vins,
        COUNT(DISTINCT license_plate) FILTER (WHERE license_plate IS NOT NULL AND license_plate != '') as unique_plates
    FROM vehicles
""")

total, unique_ids, unique_vins, unique_plates = cur.fetchone()

print(f"\nTotal Vehicles: {total}")
print(f"Unique Vehicle IDs: {unique_ids}")
print(f"Unique VINs: {unique_vins}")
print(f"Unique License Plates: {unique_plates}")

if total == unique_ids:
    print("\n✅ All vehicle IDs are unique (PRIMARY KEY working correctly)")
else:
    print(f"\n⚠️  WARNING: {total - unique_ids} duplicate vehicle IDs found!")

# Check for VIN duplicates
cur.execute("""
    SELECT vin_number, COUNT(*) as count, STRING_AGG(vehicle_id::text, ', ') as vehicle_ids
    FROM vehicles
    WHERE vin_number IS NOT NULL AND vin_number != ''
    GROUP BY vin_number
    HAVING COUNT(*) > 1
""")

vin_dups = cur.fetchall()
if vin_dups:
    print(f"\n⚠️  {len(vin_dups)} VIN numbers are used by multiple vehicles:")
    for vin, count, ids in vin_dups:
        print(f"  VIN {vin}: {count} vehicles (IDs: {ids})")
else:
    print("\n✅ All VINs are unique")

# Check for license plate duplicates
cur.execute("""
    SELECT license_plate, COUNT(*) as count, STRING_AGG(vehicle_id::text, ', ') as vehicle_ids
    FROM vehicles
    WHERE license_plate IS NOT NULL AND license_plate != ''
    GROUP BY license_plate
    HAVING COUNT(*) > 1
""")

plate_dups = cur.fetchall()
if plate_dups:
    print(f"\n⚠️  {len(plate_dups)} license plates are used by multiple vehicles:")
    for plate, count, ids in plate_dups:
        print(f"  Plate {plate}: {count} vehicles (IDs: {ids})")
else:
    print("\n✅ All license plates are unique")

print("\n" + "=" * 120)

cur.close()
conn.close()
