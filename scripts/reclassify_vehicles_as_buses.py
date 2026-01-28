#!/usr/bin/env python
"""Reclassify SUVs and shuttles with 13+ passengers as buses."""

import psycopg2
import os
import argparse

# Database connection
conn = psycopg2.connect(
    host=os.getenv('DB_HOST', 'localhost'),
    dbname=os.getenv('DB_NAME', 'almsdata'),
    user=os.getenv('DB_USER', 'postgres'),
    password=os.getenv('DB_PASSWORD', '***REMOVED***')
)
cur = conn.cursor()

parser = argparse.ArgumentParser(description='Reclassify vehicles as buses')
parser.add_argument('--write', action='store_true', help='Apply changes (default is dry-run)')
args = parser.parse_args()

print("\n" + "=" * 100)
print("VEHICLE RECLASSIFICATION - BUSES (13+ PASSENGERS)")
print("=" * 100)

# Find vehicles to reclassify
cur.execute("""
    SELECT 
        vehicle_id,
        unit_number,
        vehicle_type,
        make,
        model,
        year,
        passenger_capacity,
        license_plate
    FROM vehicles
    WHERE passenger_capacity >= 13
    ORDER BY passenger_capacity DESC, make, model
""")

vehicles = cur.fetchall()

print(f"\nFound {len(vehicles)} vehicles with 13+ passengers:")
print("-" * 100)
print(f"{'ID':<6} {'Unit#':<8} {'Current Type':<20} {'Make/Model':<30} {'Capacity':<10} {'License':<12}")
print("-" * 100)

reclassify_list = []

for vehicle_id, unit, vtype, make, model, year, capacity, plate in vehicles:
    make_model = f"{make or ''} {model or ''} {year or ''}".strip()
    print(f"{vehicle_id:<6} {unit or 'N/A':<8} {vtype or 'Unknown':<20} {make_model:<30} {capacity or 'N/A':<10} {plate or 'N/A':<12}")
    
    # Determine new vehicle_type
    new_type = None
    
    # Ford Excursion 13 passenger SUV
    if make and 'FORD' in make.upper() and model and 'EXCURSION' in model.upper() and capacity == 13:
        new_type = 'SUV Bus (13 passenger)'
    
    # Lincoln Navigator SUV 13 passenger
    elif make and 'LINCOLN' in make.upper() and model and 'NAVIGATOR' in model.upper() and capacity == 13:
        new_type = 'SUV Bus (13 passenger)'
    
    # Ford Expedition 13 passenger
    elif make and 'FORD' in make.upper() and model and 'EXPEDITION' in model.upper() and capacity == 13:
        new_type = 'SUV Bus (13 passenger)'
    
    # Ford Transit 14 passenger
    elif make and 'FORD' in make.upper() and model and 'TRANSIT' in model.upper() and capacity == 14:
        new_type = 'Shuttle Bus (14 passenger)'
    
    # 18 passenger shuttle bus
    elif capacity == 18:
        new_type = 'Shuttle Bus (18 passenger)'
    
    # Any other 13-19 passenger vehicle
    elif capacity >= 13 and capacity <= 19:
        new_type = f'Shuttle Bus ({capacity} passenger)'
    
    # 20+ passenger vehicles
    elif capacity >= 20:
        new_type = f'Bus ({capacity} passenger)'
    
    if new_type and new_type != vtype:
        reclassify_list.append((vehicle_id, vtype or 'Unknown', new_type, make_model, capacity))

print("\n" + "=" * 100)
print("VEHICLES TO RECLASSIFY:")
print("=" * 100)

if reclassify_list:
    print(f"\n{'ID':<6} {'Current Type':<25} {'New Type':<30} {'Vehicle':<30} {'Capacity':<10}")
    print("-" * 100)
    
    for vid, old_type, new_type, vehicle, capacity in reclassify_list:
        print(f"{vid:<6} {old_type:<25} {new_type:<30} {vehicle:<30} {capacity:<10}")
    
    if args.write:
        print("\n" + "=" * 100)
        print("APPLYING CHANGES...")
        print("=" * 100)
        
        # Create backup
        timestamp = __import__('datetime').datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_table = f'vehicles_backup_{timestamp}'
        
        cur.execute(f"""
            CREATE TABLE {backup_table} AS 
            SELECT * FROM vehicles 
            WHERE vehicle_id IN ({','.join([str(v[0]) for v in reclassify_list])})
        """)
        print(f"\n✅ Backup created: {backup_table} ({len(reclassify_list)} vehicles)")
        
        # Update vehicle_type
        update_count = 0
        for vid, old_type, new_type, vehicle, capacity in reclassify_list:
            cur.execute("""
                UPDATE vehicles 
                SET vehicle_type = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE vehicle_id = %s
            """, (new_type, vid))
            update_count += cur.rowcount
            print(f"  ✅ Vehicle {vid}: '{old_type}' → '{new_type}'")
        
        conn.commit()
        
        print("\n" + "=" * 100)
        print(f"✅ COMPLETE: Updated {update_count} vehicles")
        print("=" * 100)
        
        # Verify
        print("\nVERIFICATION - Current bus inventory:")
        print("-" * 100)
        
        cur.execute("""
            SELECT 
                vehicle_type,
                COUNT(*) as count,
                STRING_AGG(CONCAT(make, ' ', model, ' ', year), ', ') as vehicles
            FROM vehicles
            WHERE passenger_capacity >= 13
            GROUP BY vehicle_type
            ORDER BY vehicle_type
        """)
        
        print(f"{'Vehicle Type':<40} {'Count':<8} {'Examples':<60}")
        print("-" * 100)
        for vtype, count, examples in cur.fetchall():
            examples_short = (examples[:57] + '...') if examples and len(examples) > 60 else (examples or '')
            print(f"{vtype:<40} {count:<8} {examples_short:<60}")
        
    else:
        print("\n" + "=" * 100)
        print("DRY RUN - No changes made. Use --write to apply changes.")
        print("=" * 100)
else:
    print("\n✅ No vehicles need reclassification - all are already properly classified!")

cur.close()
conn.close()

print("\n" + "=" * 100)
