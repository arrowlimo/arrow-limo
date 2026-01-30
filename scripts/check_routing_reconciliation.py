#!/usr/bin/env python3
"""
Check LMS staging tables for routing data
Identify what routing information exists in LMS that needs to be reconciled to ALMS
"""

import psycopg2
from decimal import Decimal

DB_HOST = "localhost"
DB_NAME = "almsdata"
DB_USER = "postgres"
DB_PASSWORD = "***REMOVED***"

try:
    conn = psycopg2.connect(f"host={DB_HOST} dbname={DB_NAME} user={DB_USER} password={DB_PASSWORD}")
    cur = conn.cursor()
    
    print("="*120)
    print("LMS STAGING TABLES - ROUTING DATA ANALYSIS")
    print("="*120)
    
    # Check what columns exist in lms2026_reserves (the main charter equivalent)
    print("\nlms2026_reserves columns:")
    cur.execute("""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name = 'lms2026_reserves'
        ORDER BY ordinal_position
    """)
    
    lms_cols = cur.fetchall()
    for col_name, col_type in lms_cols:
        print(f"  {col_name:30} {col_type}")
    
    # Check charters columns for routing
    print("\n" + "="*120)
    print("ALMS charters table columns (checking for routing fields):")
    cur.execute("""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name = 'charters'
        ORDER BY ordinal_position
    """)
    
    alms_cols = cur.fetchall()
    routing_keywords = ['route', 'pickup', 'dropoff', 'address', 'location', 'time']
    for col_name, col_type in alms_cols:
        if any(kw in col_name.lower() for kw in routing_keywords):
            print(f"  {col_name:30} {col_type}")
    
    # Check if charter_routes table exists
    print("\n" + "="*120)
    print("CHECKING FOR CHARTER_ROUTES TABLE:")
    cur.execute("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables 
            WHERE table_name = 'charter_routes'
        )
    """)
    
    exists = cur.fetchone()[0]
    if exists:
        print("✅ charter_routes table EXISTS")
        
        cur.execute("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'charter_routes'
            ORDER BY ordinal_position
        """)
        
        print("\ncharter_routes columns:")
        for col_name, col_type in cur.fetchall():
            print(f"  {col_name:30} {col_type}")
        
        # Check how many routes exist
        cur.execute("SELECT COUNT(*) FROM charter_routes")
        count = cur.fetchone()[0]
        print(f"\nTotal charter_routes: {count:,}")
        
        # Check for routes with routing data
        cur.execute("""
            SELECT COUNT(*) FROM charter_routes 
            WHERE pickup_location IS NOT NULL OR dropoff_location IS NOT NULL
        """)
        
        with_routing = cur.fetchone()[0]
        print(f"Routes with location data: {with_routing:,}")
        
    else:
        print("❌ charter_routes table DOES NOT EXIST")
    
    # Check LMS reserve data for routing fields
    print("\n" + "="*120)
    print("LMS2026_RESERVES SAMPLE DATA - ROUTING FIELDS:")
    print("="*120)
    
    cur.execute("""
        SELECT 
            reserve_no,
            pickup_address,
            dropoff_address,
            pu_time,
            status
        FROM lms2026_reserves
        WHERE pickup_address IS NOT NULL OR dropoff_address IS NOT NULL
        LIMIT 10
    """)
    
    rows = cur.fetchall()
    if rows:
        for reserve_no, pickup, dropoff, pu_time, status in rows:
            print(f"\n{reserve_no}:")
            print(f"  Pickup:  {pickup[:80] if pickup else 'N/A'}")
            print(f"  Dropoff: {dropoff[:80] if dropoff else 'N/A'}")
            print(f"  Time:    {pu_time}")
            print(f"  Status:  {status}")
    else:
        print("No LMS reserves with location data found")
    
    # Check how many LMS reserves have routing data
    print("\n" + "="*120)
    print("LMS2026_RESERVES ROUTING DATA COVERAGE:")
    print("="*120)
    
    cur.execute("""
        SELECT 
            COUNT(*) as total_reserves,
            COUNT(pickup_address) as with_pickup,
            COUNT(dropoff_address) as with_dropoff,
            COUNT(pu_time) as with_time
        FROM lms2026_reserves
    """)
    
    total, with_pickup, with_dropoff, with_time = cur.fetchone()
    print(f"Total LMS reserves: {total:,}")
    print(f"With pickup address: {with_pickup:,} ({with_pickup/total*100:.1f}%)")
    print(f"With dropoff address: {with_dropoff:,} ({with_dropoff/total*100:.1f}%)")
    print(f"With pickup time: {with_time:,} ({with_time/total*100:.1f}%)")
    
    # Check ALMS charters for pickup/dropoff routing info
    print("\n" + "="*120)
    print("ALMS CHARTERS ROUTING DATA COVERAGE:")
    print("="*120)
    
    cur.execute("""
        SELECT 
            COUNT(*) as total_charters,
            COUNT(pickup_location) as with_pickup,
            COUNT(dropoff_location) as with_dropoff,
            COUNT(pickup_time) as with_time
        FROM charters
    """)
    
    total, with_pickup, with_dropoff, with_time = cur.fetchone()
    print(f"Total ALMS charters: {total:,}")
    print(f"With pickup_location: {with_pickup:,} ({with_pickup/total*100:.1f}%)")
    print(f"With dropoff_location: {with_dropoff:,} ({with_dropoff/total*100:.1f}%)")
    print(f"With pickup_time: {with_time:,} ({with_time/total*100:.1f}%)")
    
    # Sample ALMS charter routing data
    print("\n" + "="*120)
    print("ALMS CHARTERS SAMPLE ROUTING DATA:")
    print("="*120)
    
    cur.execute("""
        SELECT 
            reserve_number,
            pickup_location,
            dropoff_location,
            pickup_time,
            charter_date
        FROM charters
        WHERE pickup_location IS NOT NULL OR dropoff_location IS NOT NULL
        LIMIT 5
    """)
    
    for row in cur.fetchall():
        reserve_no, pickup, dropoff, time, date = row
        print(f"\n{reserve_no} ({date}):")
        print(f"  Pickup:  {pickup[:80] if pickup else 'N/A'}")
        print(f"  Dropoff: {dropoff[:80] if dropoff else 'N/A'}")
        print(f"  Time:    {time}")
    
    conn.close()
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
