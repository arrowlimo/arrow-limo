#!/usr/bin/env python
"""Map charter vehicle names (L-1 to L-25) to vehicle_id and update charters table."""

import psycopg2
import os
import re

conn = psycopg2.connect(
    host=os.getenv('DB_HOST', 'localhost'),
    dbname=os.getenv('DB_NAME', 'almsdata'),
    user=os.getenv('DB_USER', 'postgres'),
    password=os.getenv('DB_PASSWORD', '***REMOVED***')
)
cur = conn.cursor()

print("\n" + "=" * 100)
print("MAPPING VEHICLE NAMES TO VEHICLE_ID")
print("=" * 100)

# Check what vehicle names exist in charters
print("\n1. Checking vehicle names in charters table...")
cur.execute("""
    SELECT DISTINCT vehicle, COUNT(*) as count
    FROM charters
    WHERE vehicle IS NOT NULL AND vehicle != ''
    GROUP BY vehicle
    ORDER BY COUNT(*) DESC
    LIMIT 50
""")

vehicle_names = cur.fetchall()
print(f"Found {len(vehicle_names)} distinct vehicle names:")
for vname, count in vehicle_names[:20]:  # Show top 20
    print(f"  {vname}: {count:,} charters")

# Get all vehicles with their unit numbers
print("\n2. Getting vehicles table with unit numbers...")
cur.execute("""
    SELECT vehicle_id, unit_number, make, model, year, vehicle_type
    FROM vehicles
    ORDER BY vehicle_id
""")

vehicles = cur.fetchall()
print(f"\nVehicles in database:")
print(f"{'ID':<6} {'Unit#':<12} {'Type':<30} {'Vehicle':<40}")
print("-" * 100)
for vid, unit, make, model, year, vtype in vehicles:
    vehicle_desc = f"{make or ''} {model or ''} {year or ''}".strip()
    print(f"{vid:<6} {unit or 'N/A':<12} {vtype or 'Unknown':<30} {vehicle_desc:<40}")

# Create mapping from L-X format to vehicle_id
print("\n3. Creating L-X format mapping...")
l_pattern = re.compile(r'L-?(\d+)', re.IGNORECASE)

# Build mapping dictionary
vehicle_mapping = {}

# Map by unit_number if it matches L-X format
for vid, unit, make, model, year, vtype in vehicles:
    if unit:
        # Try to extract L-X format
        match = l_pattern.search(unit)
        if match:
            l_num = int(match.group(1))
            key = f"L-{l_num}"
            vehicle_mapping[key.upper()] = vid
            vehicle_mapping[f"L{l_num}"] = vid  # Also without dash
            print(f"  Mapped '{key}' → vehicle_id {vid}")

# Also check vehicle names in charters for L-X patterns
print("\n4. Analyzing charter vehicle name patterns...")
l_format_charters = {}
for vname, count in vehicle_names:
    match = l_pattern.search(vname)
    if match:
        l_num = int(match.group(1))
        normalized = f"L-{l_num}"
        if normalized.upper() not in l_format_charters:
            l_format_charters[normalized.upper()] = []
        l_format_charters[normalized.upper()].append((vname, count))

print(f"Found {len(l_format_charters)} L-X format patterns in charters:")
for l_key, variants in sorted(l_format_charters.items()):
    total_count = sum(count for _, count in variants)
    variant_str = ", ".join([f"'{name}' ({count})" for name, count in variants])
    mapped_id = vehicle_mapping.get(l_key, 'UNMAPPED')
    print(f"  {l_key} → vehicle_id {mapped_id}: {total_count:,} charters - variants: {variant_str}")

# Count how many charters we can map
print("\n5. Counting mappable charters...")
cur.execute("""
    SELECT vehicle, COUNT(*) as count
    FROM charters
    WHERE vehicle IS NOT NULL AND vehicle != ''
    GROUP BY vehicle
""")

total_charters_with_vehicle = 0
mappable_charters = 0
unmappable_charters = 0

for vname, count in cur.fetchall():
    total_charters_with_vehicle += count
    match = l_pattern.search(vname)
    if match:
        l_num = int(match.group(1))
        key = f"L-{l_num}"
        if key.upper() in vehicle_mapping:
            mappable_charters += count
        else:
            unmappable_charters += count
            print(f"  ⚠️  Cannot map '{vname}' (L-{l_num}) - no matching vehicle_id")
    else:
        unmappable_charters += count

print(f"\nTotal charters with vehicle name: {total_charters_with_vehicle:,}")
print(f"Mappable charters: {mappable_charters:,} ({mappable_charters/total_charters_with_vehicle*100:.1f}%)")
print(f"Unmappable charters: {unmappable_charters:,} ({unmappable_charters/total_charters_with_vehicle*100:.1f}%)")

# Dry run - show what would be updated
print("\n" + "=" * 100)
print("DRY RUN - Sample updates that would be performed:")
print("=" * 100)

cur.execute("""
    SELECT charter_id, reserve_number, charter_date, vehicle
    FROM charters
    WHERE vehicle IS NOT NULL AND vehicle != ''
    AND vehicle_id IS NULL
    ORDER BY charter_date DESC
    LIMIT 20
""")

sample_updates = []
for charter_id, reserve_num, charter_date, vname in cur.fetchall():
    match = l_pattern.search(vname)
    if match:
        l_num = int(match.group(1))
        key = f"L-{l_num}"
        if key.upper() in vehicle_mapping:
            vid = vehicle_mapping[key.upper()]
            sample_updates.append((charter_id, reserve_num, charter_date, vname, vid))

print(f"{'Charter':<10} {'Reserve#':<12} {'Date':<12} {'Vehicle Name':<20} {'→ ID':<6}")
print("-" * 100)
for charter_id, reserve_num, charter_date, vname, vid in sample_updates:
    print(f"{charter_id:<10} {reserve_num or 'N/A':<12} {str(charter_date):<12} {vname:<20} {vid:<6}")

# Ask for confirmation
print("\n" + "=" * 100)
print("READY TO UPDATE")
print("=" * 100)
print(f"\nThis will update vehicle_id for {mappable_charters:,} charters")
print("\nTo apply these changes, run:")
print("  python -X utf8 scripts/map_charter_vehicles.py --write")

cur.close()
conn.close()
