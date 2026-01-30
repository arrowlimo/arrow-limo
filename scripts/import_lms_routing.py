#!/usr/bin/env python3
"""
Import LMS routing data to ALMS charter_routes table
LMS has detailed multi-stop routing with addresses, times, and sequence
"""

import psycopg2
from datetime import time as dt_time

DB_HOST = "localhost"
DB_NAME = "almsdata"
DB_USER = "postgres"
DB_PASSWORD = "***REDACTED***"

try:
    conn = psycopg2.connect(f"host={DB_HOST} dbname={DB_NAME} user={DB_USER} password={DB_PASSWORD}")
    cur = conn.cursor()
    
    print("="*140)
    print("IMPORT LMS ROUTING DATA TO CHARTER_ROUTES")
    print("="*140)
    
    # Check if LMS routing data exists
    cur.execute("""
        SELECT COUNT(*) FROM lms2026_reserves 
        WHERE raw_data->'routing' IS NOT NULL
    """)
    
    routing_count = cur.fetchone()[0]
    print(f"\nLMS reserves with routing data in raw_data: {routing_count:,}")
    
    # Check what routing information is available in lms2026_reserves
    cur.execute("""
        SELECT column_name FROM information_schema.columns 
        WHERE table_name = 'lms2026_reserves'
        AND column_name ILIKE '%route%' OR column_name ILIKE '%routing%'
    """)
    
    routing_cols = [row[0] for row in cur.fetchall()]
    print(f"LMS routing columns: {routing_cols if routing_cols else 'None found'}")
    
    # Check if there's a separate lms2026_routing table
    cur.execute("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables 
            WHERE table_name = 'lms2026_routing'
        )
    """)
    
    routing_table_exists = cur.fetchone()[0]
    if routing_table_exists:
        print("\n✅ lms2026_routing table EXISTS")
        
        # Get table structure
        cur.execute("""
            SELECT column_name, data_type FROM information_schema.columns 
            WHERE table_name = 'lms2026_routing'
            ORDER BY ordinal_position
        """)
        
        print("\nlms2026_routing columns:")
        for col_name, col_type in cur.fetchall():
            print(f"  {col_name:30} {col_type}")
        
        # Check row count
        cur.execute("SELECT COUNT(*) FROM lms2026_routing")
        row_count = cur.fetchone()[0]
        print(f"\nTotal routing records: {row_count:,}")
        
        # Show sample routing data
        print("\n" + "-"*140)
        print("SAMPLE LMS ROUTING DATA:")
        print("-"*140)
        
        cur.execute("""
            SELECT 
                reserve_no,
                route_id,
                route_order,
                route_type,
                pu_time,
                pickup_address,
                dropoff_address,
                poi_name
            FROM lms2026_routing
            WHERE reserve_no IN ('001009', '019551', '019718')
            LIMIT 15
        """)
        
        for reserve, route_id, order, rtype, time, pickup, dropoff, poi in cur.fetchall():
            print(f"\n{reserve} - RouteID {route_id} (Order {order}, Type {rtype}):")
            print(f"  Time: {time}")
            print(f"  Pickup:  {pickup[:60] if pickup else 'N/A'}")
            print(f"  Dropoff: {dropoff[:60] if dropoff else 'N/A'}")
            if poi:
                print(f"  POI:     {poi[:60]}")
        
        # Check coverage - how many charters have LMS routing vs ALMS routes
        print("\n" + "="*140)
        print("ROUTING COVERAGE ANALYSIS")
        print("="*140)
        
        cur.execute("""
            SELECT COUNT(DISTINCT reserve_no) FROM lms2026_routing
        """)
        lms_routing_charters = cur.fetchone()[0]
        print(f"LMS charters with routing data: {lms_routing_charters:,}")
        
        cur.execute("""
            SELECT COUNT(DISTINCT reserve_no) FROM lms2026_reserves
            WHERE reserve_no IN (SELECT reserve_no FROM lms2026_routing)
        """)
        lms_charters_with_routing = cur.fetchone()[0]
        
        # Check ALMS coverage
        cur.execute("""
            SELECT COUNT(*) FROM charters c
            WHERE c.reserve_number IN (SELECT DISTINCT reserve_no FROM lms2026_routing)
        """)
        alms_charters_to_update = cur.fetchone()[0]
        print(f"These charters already in ALMS: {alms_charters_to_update:,}")
        
        # Sample single charter routing
        print("\n" + "-"*140)
        print("FULL ROUTING FOR CHARTER 001009:")
        print("-"*140)
        
        cur.execute("""
            SELECT 
                route_id,
                route_order,
                route_type,
                pu_time,
                pickup_address,
                dropoff_address,
                poi_name,
                notes
            FROM lms2026_routing
            WHERE reserve_no = '001009'
            ORDER BY route_order
        """)
        
        routes = cur.fetchall()
        for route_id, order, rtype, time, pickup, dropoff, poi, notes in routes:
            type_label = "PICKUP" if rtype == 'P' else "DROPOFF"
            print(f"\nStop {order} - {type_label} (RouteID {route_id}):")
            print(f"  Time: {time}")
            if pickup:
                print(f"  Address: {pickup}")
            if poi:
                print(f"  POI:     {poi}")
            if dropoff:
                print(f"  Return:  {dropoff}")
            if notes:
                print(f"  Notes:   {notes[:80]}")
        
    else:
        print("\n❌ lms2026_routing table does NOT exist")
        print("   Routing data may be in raw_data JSONB column of lms2026_reserves")
    
    conn.close()
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
