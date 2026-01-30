"""
Check LMS database for vehicle L-X format mapping information.
"""

import pyodbc
import psycopg2
import os

# LMS Access database connection
LMS_PATH = r'L:\limo\backups\lms.mdb'
conn_str = f'DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={LMS_PATH};'

try:
    lms_conn = pyodbc.connect(conn_str)
    lms_cur = lms_conn.cursor()
    
    print("=" * 100)
    print("LMS VEHICLE MAPPING ANALYSIS")
    print("=" * 100)
    
    # Check what tables exist
    print("\n1. Skipping table enumeration (permissions issue)...")
    vehicle_tables = ['Vehicle']  # Known table name
    
    # Check Reserve table for vehicle field
    print("\n2. Checking Reserve table vehicle field...")
    lms_cur.execute("SELECT TOP 20 Reserve_No, Vehicle FROM Reserve WHERE Vehicle IS NOT NULL ORDER BY PU_Date DESC")
    reserves = lms_cur.fetchall()
    print(f"Sample vehicle names from LMS Reserve table:")
    for reserve_no, vehicle in reserves:
        print(f"  Reserve {reserve_no}: '{vehicle}'")
    
    # Get distinct vehicle values
    print("\n3. Getting distinct vehicle names from LMS...")
    lms_cur.execute("SELECT DISTINCT Vehicle FROM Reserve WHERE Vehicle IS NOT NULL ORDER BY Vehicle")
    lms_vehicles = [row[0] for row in lms_cur.fetchall()]
    print(f"Found {len(lms_vehicles)} distinct vehicle names:")
    for i, v in enumerate(lms_vehicles[:30], 1):  # Show first 30
        print(f"  {i}. '{v}'")
    if len(lms_vehicles) > 30:
        print(f"  ... and {len(lms_vehicles) - 30} more")
    
    # Check if there's a vehicles/units table
    if vehicle_tables:
        print(f"\n4. Checking {vehicle_tables[0]} table structure...")
        lms_cur.execute(f"SELECT TOP 5 * FROM {vehicle_tables[0]}")
        rows = lms_cur.fetchall()
        if rows:
            columns = [col[0] for col in lms_cur.description]
            print(f"Columns: {', '.join(columns)}")
            print("\nSample rows:")
            for row in rows:
                print(f"  {dict(zip(columns, row))}")
    
    lms_cur.close()
    lms_conn.close()
    
    # Now check PostgreSQL vehicles
    print("\n" + "=" * 100)
    print("POSTGRESQL VEHICLES CURRENT STATE")
    print("=" * 100)
    
    pg_conn = psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REDACTED***')
    )
    pg_cur = pg_conn.cursor()
    
    pg_cur.execute("""
        SELECT vehicle_id, unit_number, make, model, year, vehicle_type, 
               passenger_capacity, vin_number, license_plate
        FROM vehicles 
        ORDER BY vehicle_id
    """)
    
    print("\nCurrent vehicles in PostgreSQL:")
    print(f"{'ID':<4} {'Unit#':<10} {'Type':<30} {'Make/Model/Year':<40} {'VIN':<18} {'Plate':<10}")
    print("-" * 130)
    for row in pg_cur.fetchall():
        vid, unit, make, model, year, vtype, pax, vin, plate = row
        unit_str = unit if unit else 'N/A'
        vtype_str = (vtype[:28] + '..') if vtype and len(vtype) > 30 else (vtype if vtype else 'Unknown')
        vehicle_str = f"{make or ''} {model or ''} {year or ''}".strip()
        vin_str = (vin[-8:] if vin and len(vin) > 8 else vin) if vin else 'N/A'
        plate_str = plate if plate else 'N/A'
        print(f"{vid:<4} {unit_str:<10} {vtype_str:<30} {vehicle_str:<40} {vin_str:<18} {plate_str:<10}")
    
    pg_cur.close()
    pg_conn.close()
    
    print("\n" + "=" * 100)
    print("SUMMARY")
    print("=" * 100)
    print(f"✓ LMS has {len(lms_vehicles)} distinct vehicle identifiers")
    print(f"✓ PostgreSQL has vehicles with unit_number mostly 'N/A'")
    print(f"✓ Need to create mapping between LMS vehicle names and PostgreSQL vehicle_id")
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
