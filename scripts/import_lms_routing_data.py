#!/usr/bin/env python3
"""
Import LMS routing data to ALMS charter_routes table
LMS Routing table has detailed multi-stop routing with 51,035 records
"""

import pyodbc
import psycopg2
from datetime import datetime, time as dt_time

LMS_PATH = r'L:\limo\database_backups\lms2026.mdb'
PG_HOST = "localhost"
PG_DB = "almsdata"
PG_USER = "postgres"
PG_PASSWORD = "***REMOVED***"

def connect_lms():
    """Connect to LMS Access database"""
    try:
        conn_str = rf'DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={LMS_PATH};'
        return pyodbc.connect(conn_str)
    except Exception as e:
        print(f"❌ Could not connect to LMS: {e}")
        return None

def connect_postgres():
    """Connect to PostgreSQL"""
    return psycopg2.connect(
        host=PG_HOST,
        dbname=PG_DB,
        user=PG_USER,
        password=PG_PASSWORD
    )

def extract_time(value):
    """Extract time from datetime (Access stores as 1899-12-30 HH:MM:SS)"""
    if value is None:
        return None
    if isinstance(value, dt_time):
        return value
    if isinstance(value, datetime):
        return value.time()
    return None

try:
    lms_conn = connect_lms()
    if not lms_conn:
        exit(1)
    
    pg_conn = connect_postgres()
    
    lms_cur = lms_conn.cursor()
    pg_cur = pg_conn.cursor()
    
    print("="*140)
    print("IMPORT LMS ROUTING DATA TO CHARTER_ROUTES")
    print("="*140)
    
    # Get all LMS routing data
    print("\nExtracting routing data from LMS...")
    lms_cur.execute("""
        SELECT 
            Reserve_No,
            [Order],
            Type,
            Time,
            Line1,
            Street,
            City,
            RouteId,
            RouteType,
            POIName,
            Notes
        FROM Routing
        ORDER BY Reserve_No, [Order]
    """)
    
    lms_routing = lms_cur.fetchall()
    print(f"Extracted {len(lms_routing):,} routing records from LMS")
    
    # Map reserve numbers to charter_ids
    print("\nMapping reserve numbers to charter IDs...")
    
    # Get list of reserve numbers from routing
    reserve_numbers = set(row[0] for row in lms_routing)
    print(f"Unique reserves in routing: {len(reserve_numbers):,}")
    
    # Build mapping for all reserves
    all_reserves_list = list(reserve_numbers)
    charter_mapping = {}
    
    # Process in batches
    batch_size = 100
    for i in range(0, len(all_reserves_list), batch_size):
        batch = all_reserves_list[i:i+batch_size]
        placeholders = ','.join([f"'{r}'" for r in batch])
        pg_cur.execute(f"""
            SELECT reserve_number, charter_id 
            FROM charters 
            WHERE reserve_number IN ({placeholders})
        """)
        
        for reserve_no, charter_id in pg_cur.fetchall():
            charter_mapping[reserve_no] = charter_id
    
    print(f"Found {len(charter_mapping):,} matching charters in ALMS")
    
    # Insert routing data
    print("\n" + "="*140)
    print("IMPORTING ROUTING DATA")
    print("="*140)
    
    insert_count = 0
    skip_count = 0
    error_count = 0
    
    # Group by reserve_number and order
    routing_by_reserve = {}
    for routing_row in lms_routing:
        reserve_no = routing_row[0]
        if reserve_no not in routing_by_reserve:
            routing_by_reserve[reserve_no] = []
        routing_by_reserve[reserve_no].append(routing_row)
    
    for reserve_no in sorted(routing_by_reserve.keys())[:10]:  # Start with first 10
        charter_id = charter_mapping.get(reserve_no)
        if not charter_id:
            skip_count += len(routing_by_reserve[reserve_no])
            continue
        
        print(f"\n{reserve_no} ({charter_id}): {len(routing_by_reserve[reserve_no])} routes")
        
        for routing_row in routing_by_reserve[reserve_no]:
            reserve_no, order, rtype, time, line1, street, city, route_id, route_type, poi, notes = routing_row
            
            # Extract pickup/dropoff locations
            if rtype == 'P':
                pickup_location = line1
                dropoff_location = None
                pickup_time = extract_time(time)
                dropoff_time = None
            else:  # D
                pickup_location = None
                dropoff_location = line1
                pickup_time = None
                dropoff_time = extract_time(time)
            
            try:
                pg_cur.execute("""
                    INSERT INTO charter_routes (
                        charter_id,
                        route_sequence,
                        pickup_location,
                        pickup_time,
                        dropoff_location,
                        dropoff_time,
                        route_notes,
                        created_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                """, (
                    charter_id,
                    order,
                    pickup_location,
                    pickup_time,
                    dropoff_location,
                    dropoff_time,
                    notes[:500] if notes else None
                ))
                insert_count += 1
                print(f"  ✅ Route {order}: {pickup_location or dropoff_location}")
                
            except Exception as e:
                error_count += 1
                print(f"  ❌ Route {order} error: {e}")
    
    # Commit
    pg_conn.commit()
    print(f"\n✅ Committed {insert_count} routing records")
    print(f"⏭️  Skipped {skip_count} (no matching charter)")
    print(f"❌ Errors: {error_count}")
    
    # Show sample result
    print("\n" + "="*140)
    print("SAMPLE: Charter 001009 routing after import")
    print("="*140)
    
    pg_cur.execute("""
        SELECT 
            route_sequence,
            pickup_location,
            pickup_time,
            dropoff_location,
            dropoff_time
        FROM charter_routes
        WHERE charter_id = (SELECT charter_id FROM charters WHERE reserve_number = '001009' LIMIT 1)
        ORDER BY route_sequence
    """)
    
    for seq, pickup, pu_time, dropoff, do_time in pg_cur.fetchall():
        print(f"\nRoute {seq}:")
        if pickup:
            print(f"  Pickup: {pickup} @ {pu_time}")
        if dropoff:
            print(f"  Dropoff: {dropoff} @ {do_time}")
    
    lms_conn.close()
    pg_conn.close()
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
