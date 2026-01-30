#!/usr/bin/env python3
"""
Smart import of LMS routing data - updates existing, adds missing
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
    print("SMART IMPORT: UPDATE & ADD LMS ROUTING DATA")
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
            RouteId,
            POIName,
            Notes
        FROM Routing
        WHERE Reserve_No = '001009'
        ORDER BY Reserve_No, [Order]
    """)
    
    lms_routing = lms_cur.fetchall()
    print(f"Extracted {len(lms_routing):,} routing records for 001009 from LMS")
    
    # Get charter_id for 001009
    pg_cur.execute("SELECT charter_id FROM charters WHERE reserve_number = '001009' LIMIT 1")
    charter_id = pg_cur.fetchone()[0]
    print(f"Charter ID: {charter_id}")
    
    # Get existing routes
    pg_cur.execute("""
        SELECT route_id, route_sequence FROM charter_routes 
        WHERE charter_id = %s
        ORDER BY route_sequence
    """, (charter_id,))
    
    existing_routes = {row[1]: row[0] for row in pg_cur.fetchall()}
    print(f"Existing routes in ALMS: {len(existing_routes)} (sequences: {list(existing_routes.keys())})")
    
    # Process and update/insert routes
    print("\n" + "="*140)
    print("PROCESSING ROUTING DATA")
    print("="*140)
    
    update_count = 0
    insert_count = 0
    
    for lms_row in lms_routing:
        reserve_no, order, rtype, time, line1, route_id, poi, notes = lms_row
        
        # Extract fields
        pickup_location = line1 if rtype == 'P' else None
        dropoff_location = line1 if rtype == 'D' else None
        pickup_time = extract_time(time) if rtype == 'P' else None
        dropoff_time = extract_time(time) if rtype == 'D' else None
        
        if order in existing_routes:
            # UPDATE existing route
            existing_route_id = existing_routes[order]
            pg_cur.execute("""
                UPDATE charter_routes 
                SET 
                    pickup_location = COALESCE(%s, pickup_location),
                    pickup_time = COALESCE(%s, pickup_time),
                    dropoff_location = COALESCE(%s, dropoff_location),
                    dropoff_time = COALESCE(%s, dropoff_time),
                    route_notes = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE route_id = %s
            """, (
                pickup_location,
                pickup_time,
                dropoff_location,
                dropoff_time,
                notes[:500] if notes else None,
                existing_route_id
            ))
            update_count += 1
            print(f"✏️  Updated Route {order}: {pickup_location or dropoff_location}")
        else:
            # INSERT new route
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
            print(f"➕ Inserted Route {order}: {pickup_location or dropoff_location}")
    
    # Commit
    pg_conn.commit()
    print(f"\n✅ Updated: {update_count}")
    print(f"✅ Inserted: {insert_count}")
    
    # Show final result
    print("\n" + "="*140)
    print("FINAL: Charter 001009 routing after update/insert")
    print("="*140)
    
    pg_cur.execute("""
        SELECT 
            route_sequence,
            pickup_location,
            pickup_time,
            dropoff_location,
            dropoff_time
        FROM charter_routes
        WHERE charter_id = %s
        ORDER BY route_sequence
    """, (charter_id,))
    
    for seq, pickup, pu_time, dropoff, do_time in pg_cur.fetchall():
        print(f"\nRoute {seq}:")
        if pickup:
            print(f"  Pickup:  {pickup} @ {pu_time}")
        if dropoff:
            print(f"  Dropoff: {dropoff} @ {do_time}")
    
    lms_conn.close()
    pg_conn.close()
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
