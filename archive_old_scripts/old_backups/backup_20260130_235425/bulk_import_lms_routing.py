"""
Bulk import LMS routing data to charter_routes
- Imports all 51,035 routing events from LMS
- Maps to new event-based schema with route_event_types
- Updates existing routes, adds new ones
"""

import os
import pyodbc
import psycopg2
from datetime import datetime, time as dt_time

# LMS Access DB
LMS_DB_PATH = r"L:\limo\database_backups\lms2026.mdb"
lms_conn_str = r'DRIVER={Microsoft Access Driver (*.mdb, *.accdb)};' + f'DBQ={LMS_DB_PATH};'

# ALMS PostgreSQL
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REDACTED***")

def extract_time(value):
    """Extract time from datetime (Access stores as 1899-12-30 HH:MM:SS)"""
    if value is None:
        return None
    if isinstance(value, dt_time):
        return value
    if isinstance(value, datetime):
        return value.time()
    return None

def map_event_type(lms_type):
    """Map LMS Type (P/D) to route_event_types"""
    if lms_type == 'P':
        return 'pickup'
    elif lms_type == 'D':
        return 'dropoff'
    else:
        return 'stop'  # Fallback for other types

def get_charter_mapping():
    """Get reserve_number to charter_id mapping"""
    pg_conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    pg_cur = pg_conn.cursor()
    
    pg_cur.execute("""
        SELECT reserve_number, charter_id
        FROM charters
        WHERE reserve_number IS NOT NULL
    """)
    
    charter_map = {row[0]: row[1] for row in pg_cur.fetchall()}
    
    pg_cur.close()
    pg_conn.close()
    
    return charter_map

def import_routing(dry_run=True, limit=None):
    """Bulk import LMS routing data"""
    
    print("="*80)
    print("LMS ROUTING BULK IMPORT")
    print("="*80)
    print(f"Mode: {'DRY RUN' if dry_run else 'LIVE IMPORT'}")
    if limit:
        print(f"Limit: {limit} routes")
    print()
    
    # Get charter mapping
    print("Building charter mapping...")
    charter_map = get_charter_mapping()
    print(f"✅ Mapped {len(charter_map)} charters\n")
    
    # Get LMS routing data
    print("Fetching LMS routing data...")
    lms_conn = pyodbc.connect(lms_conn_str)
    lms_cur = lms_conn.cursor()
    
    query = """
        SELECT 
            Reserve_No,
            [Order],
            Type,
            Time,
            Line1,
            POIName
        FROM Routing
        ORDER BY Reserve_No, [Order]
    """
    
    if limit:
        query = query.replace("SELECT ", f"SELECT TOP {limit} ")
    
    lms_cur.execute(query)
    lms_routing = lms_cur.fetchall()
    
    lms_cur.close()
    lms_conn.close()
    
    print(f"✅ Found {len(lms_routing)} routing events\n")
    
    # Group by reserve number
    routes_by_charter = {}
    for route in lms_routing:
        reserve_no = route.Reserve_No
        if reserve_no not in routes_by_charter:
            routes_by_charter[reserve_no] = []
        routes_by_charter[reserve_no].append(route)
    
    print(f"Grouped into {len(routes_by_charter)} charters\n")
    
    # Process routes
    pg_conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    pg_cur = pg_conn.cursor()
    
    charters_processed = 0
    routes_inserted = 0
    routes_updated = 0
    routes_skipped_no_charter = 0
    errors = []
    
    print("Processing routing data...")
    print("-" * 80)
    
    for reserve_no, routes in routes_by_charter.items():
        charter_id = charter_map.get(reserve_no)
        
        if not charter_id:
            routes_skipped_no_charter += len(routes)
            continue
        
        # Process each route for this charter
        for route in routes:
            sequence = route.Order if route.Order else 1
            route_type_lms = route.Type
            stop_time = extract_time(route.Time)
            address = route.Line1 or route.POIName or ''
            
            event_type_code = map_event_type(route_type_lms)
            
            # Check if route exists
            pg_cur.execute("""
                SELECT route_id, address
                FROM charter_routes
                WHERE charter_id = %s AND route_sequence = %s
            """, (charter_id, sequence))
            
            existing = pg_cur.fetchone()
            
            try:
                if existing:
                    # Update existing route
                    if not dry_run:
                        pg_cur.execute("""
                            UPDATE charter_routes
                            SET event_type_code = %s,
                                address = %s,
                                stop_time = %s,
                                reserve_number = %s,
                                updated_at = NOW()
                            WHERE route_id = %s
                        """, (event_type_code, address, stop_time, reserve_no, existing[0]))
                    routes_updated += 1
                else:
                    # Insert new route
                    if not dry_run:
                        pg_cur.execute("""
                            INSERT INTO charter_routes (
                                charter_id,
                                route_sequence,
                                event_type_code,
                                address,
                                stop_time,
                                reserve_number,
                                created_at,
                                updated_at
                            ) VALUES (%s, %s, %s, %s, %s, %s, NOW(), NOW())
                        """, (charter_id, sequence, event_type_code, address, stop_time, reserve_no))
                    routes_inserted += 1
                
            except Exception as e:
                errors.append(f"{reserve_no} seq {sequence}: {e}")
                if len(errors) <= 5:
                    print(f"  ❌ {reserve_no} seq {sequence}: {e}")
        
        charters_processed += 1
        
        if charters_processed <= 5:
            route_count = len(routes)
            print(f"  ✅ {reserve_no}: {route_count} routes")
        elif charters_processed % 1000 == 0:
            print(f"  ... {charters_processed} charters processed ({routes_inserted + routes_updated} routes)")
    
    if not dry_run:
        pg_conn.commit()
    
    pg_cur.close()
    pg_conn.close()
    
    # Summary
    print()
    print("="*80)
    print("IMPORT SUMMARY")
    print("="*80)
    print(f"Total LMS routing events: {len(lms_routing)}")
    print(f"Charters processed: {charters_processed}")
    print(f"✅ Routes inserted: {routes_inserted}")
    print(f"✅ Routes updated: {routes_updated}")
    print(f"⚠️  Skipped (no charter match): {routes_skipped_no_charter}")
    print(f"❌ Errors: {len(errors)}")
    
    if errors:
        print("\nFirst 10 errors:")
        for err in errors[:10]:
            print(f"  {err}")
    
    if not dry_run:
        print()
        print("✅ IMPORT COMPLETE - routing data committed to database")
    else:
        print()
        print("ℹ️  DRY RUN - no data written. Run with --write to commit.")

if __name__ == "__main__":
    import sys
    
    dry_run = '--write' not in sys.argv
    
    # Check for limit argument
    limit = None
    for arg in sys.argv:
        if arg.startswith('--limit='):
            limit = int(arg.split('=')[1])
    
    import_routing(dry_run=dry_run, limit=limit)
