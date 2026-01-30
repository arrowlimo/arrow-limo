#!/usr/bin/env python3
"""
Create LMS Vehicle ID → PostgreSQL vehicle_id mapping using VIN matching.

Creates a reference table for charter vehicle matching:
- LMS Reserve.Vehicle (Limo01, Limo18, etc.) 
- Maps to PostgreSQL vehicles.vehicle_id
- Using VIN as the matching key

This allows charters imported from LMS to link to correct vehicle_id.
"""

import pyodbc
import psycopg2
import os
import sys

LMS_PATH = r'L:\limo\backups\lms.mdb'

def get_lms_vehicles():
    """Get all vehicles from LMS with their VINs."""
    conn_str = f'DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={LMS_PATH};'
    conn = pyodbc.connect(conn_str)
    cur = conn.cursor()
    
    cur.execute("""
        SELECT Vehicle, Make, Model, Year, VIN, License_No
        FROM Vehicles
        WHERE VIN IS NOT NULL
        ORDER BY Vehicle
    """)
    
    vehicles = []
    for row in cur.fetchall():
        vehicles.append({
            'lms_vehicle_id': row.Vehicle,
            'make': row.Make,
            'model': row.Model,
            'year': row.Year,
            'vin': row.VIN,
            'license': row.License_No
        })
    
    cur.close()
    conn.close()
    return vehicles

def get_pg_vehicles():
    """Get all vehicles from PostgreSQL with their VINs."""
    conn = psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REDACTED***')
    )
    cur = conn.cursor()
    
    cur.execute("""
        SELECT vehicle_id, unit_number, make, model, year, vin_number, license_plate
        FROM vehicles
        WHERE vin_number IS NOT NULL
        ORDER BY vehicle_id
    """)
    
    vehicles = []
    for row in cur.fetchall():
        vehicles.append({
            'vehicle_id': row[0],
            'unit_number': row[1],
            'make': row[2],
            'model': row[3],
            'year': row[4],
            'vin': row[5],
            'license': row[6]
        })
    
    cur.close()
    conn.close()
    return vehicles

def normalize_vin(vin):
    """Normalize VIN for comparison - uppercase, no spaces/dashes."""
    if not vin:
        return None
    return str(vin).upper().replace(' ', '').replace('-', '').strip()

def create_mapping():
    """Create mapping between LMS vehicle IDs and PostgreSQL vehicle_ids."""
    print("=" * 100)
    print("LMS VEHICLE ID → POSTGRESQL vehicle_id MAPPING (VIN-BASED)")
    print("=" * 100)
    
    print("\n1. Loading LMS vehicles...")
    lms_vehicles = get_lms_vehicles()
    print(f"   Found {len(lms_vehicles)} LMS vehicles with VINs")
    
    print("\n2. Loading PostgreSQL vehicles...")
    pg_vehicles = get_pg_vehicles()
    print(f"   Found {len(pg_vehicles)} PostgreSQL vehicles with VINs")
    
    # Create VIN lookup for PostgreSQL vehicles
    pg_vin_map = {}
    for v in pg_vehicles:
        norm_vin = normalize_vin(v['vin'])
        if norm_vin:
            pg_vin_map[norm_vin] = v
    
    print(f"\n3. Matching by VIN...")
    print(f"\n{'LMS Vehicle':<15} {'VIN':<18} {'PG vehicle_id':<15} {'Unit#':<10} {'Vehicle':<40}")
    print("-" * 100)
    
    mappings = []
    matched = 0
    unmatched = []
    
    for lms_v in lms_vehicles:
        norm_vin = normalize_vin(lms_v['vin'])
        
        if norm_vin and norm_vin in pg_vin_map:
            pg_v = pg_vin_map[norm_vin]
            vehicle_desc = f"{pg_v['make'] or ''} {pg_v['model'] or ''} {pg_v['year'] or ''}".strip()
            unit = pg_v['unit_number'] or 'N/A'
            vin_short = norm_vin[-8:] if len(norm_vin) > 8 else norm_vin
            
            print(f"{lms_v['lms_vehicle_id']:<15} {vin_short:<18} {pg_v['vehicle_id']:<15} {unit:<10} {vehicle_desc:<40}")
            
            mappings.append({
                'lms_vehicle_id': lms_v['lms_vehicle_id'],
                'vehicle_id': pg_v['vehicle_id'],
                'vin': norm_vin,
                'make': pg_v['make'],
                'model': pg_v['model'],
                'year': pg_v['year']
            })
            matched += 1
        else:
            unmatched.append(lms_v)
    
    print(f"\n{'=' * 100}")
    print(f"MATCHING SUMMARY")
    print(f"{'=' * 100}")
    print(f"LMS vehicles: {len(lms_vehicles)}")
    print(f"PostgreSQL vehicles: {len(pg_vehicles)}")
    print(f"Matched by VIN: {matched} ({matched/len(lms_vehicles)*100:.1f}%)")
    print(f"Unmatched: {len(unmatched)}")
    
    if unmatched:
        print(f"\nUnmatched LMS vehicles:")
        for v in unmatched:
            vin_short = normalize_vin(v['vin'])[-8:] if v['vin'] else 'NO VIN'
            # BusHost is not a real vehicle - it's a placeholder for tracking hosts/staff
            if v['lms_vehicle_id'] == 'BusHost':
                print(f"  {v['lms_vehicle_id']:<15} {vin_short:<18} (Personnel placeholder - not a vehicle)")
            else:
                print(f"  {v['lms_vehicle_id']:<15} {vin_short:<18} {v['make']} {v['model']} {v['year']}")
    
    return mappings

def create_lookup_table(mappings, write=False):
    """Create lms_vehicle_mapping table in PostgreSQL."""
    if not write:
        print("\n" + "=" * 100)
        print("DRY RUN - Would create lms_vehicle_mapping table with:")
        print("=" * 100)
        for m in mappings[:10]:
            print(f"  {m['lms_vehicle_id']} → vehicle_id {m['vehicle_id']}")
        if len(mappings) > 10:
            print(f"  ... and {len(mappings)-10} more")
        print("\nRun with --write to create the table")
        return
    
    conn = psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REDACTED***')
    )
    cur = conn.cursor()
    
    print("\n" + "=" * 100)
    print("CREATING lms_vehicle_mapping TABLE")
    print("=" * 100)
    
    # Drop existing table if exists
    cur.execute("DROP TABLE IF EXISTS lms_vehicle_mapping")
    
    # Create mapping table
    cur.execute("""
        CREATE TABLE lms_vehicle_mapping (
            lms_vehicle_id VARCHAR(50) PRIMARY KEY,
            vehicle_id INTEGER NOT NULL REFERENCES vehicles(vehicle_id),
            vin_number VARCHAR(17),
            make VARCHAR(100),
            model VARCHAR(100),
            year INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            notes TEXT
        )
    """)
    
    print("✓ Created table structure")
    
    # Insert mappings
    for m in mappings:
        cur.execute("""
            INSERT INTO lms_vehicle_mapping 
            (lms_vehicle_id, vehicle_id, vin_number, make, model, year, notes)
            VALUES (%s, %s, %s, %s, %s, %s, 'Matched by VIN')
        """, (m['lms_vehicle_id'], m['vehicle_id'], m['vin'], 
              m['make'], m['model'], m['year']))
    
    conn.commit()
    print(f"✓ Inserted {len(mappings)} mappings")
    
    # Verify
    cur.execute("SELECT COUNT(*) FROM lms_vehicle_mapping")
    count = cur.fetchone()[0]
    print(f"✓ Verified {count} mappings in table")
    
    # Show sample
    cur.execute("""
        SELECT lvm.lms_vehicle_id, lvm.vehicle_id, v.unit_number, v.make, v.model, v.year
        FROM lms_vehicle_mapping lvm
        JOIN vehicles v ON v.vehicle_id = lvm.vehicle_id
        ORDER BY lvm.lms_vehicle_id
        LIMIT 10
    """)
    
    print("\nSample mappings:")
    print(f"{'LMS Vehicle':<15} {'vehicle_id':<12} {'Unit#':<10} {'Vehicle':<40}")
    print("-" * 80)
    for row in cur.fetchall():
        lms_id, vid, unit, make, model, year = row
        vehicle_desc = f"{make or ''} {model or ''} {year or ''}".strip()
        print(f"{lms_id:<15} {vid:<12} {unit or 'N/A':<10} {vehicle_desc:<40}")
    
    cur.close()
    conn.close()

def main():
    write_mode = '--write' in sys.argv
    
    mappings = create_mapping()
    
    if mappings:
        create_lookup_table(mappings, write=write_mode)
    else:
        print("\n✗ No mappings created - cannot proceed")
        sys.exit(1)

if __name__ == '__main__':
    main()
