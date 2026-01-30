#!/usr/bin/env python3
"""
Extract and import LMS routing data directly from Access database
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

try:
    lms_conn = connect_lms()
    if not lms_conn:
        exit(1)
    
    pg_conn = connect_postgres()
    
    lms_cur = lms_conn.cursor()
    pg_cur = pg_conn.cursor()
    
    print("="*140)
    print("EXTRACT AND IMPORT LMS ROUTING DATA")
    print("="*140)
    
    # Check for Routing table specifically
    try:
        lms_cur.execute("SELECT COUNT(*) FROM Routing")
        count = lms_cur.fetchone()[0]
        print(f"\n✅ Found 'Routing' table with {count:,} rows")
        
        # Get Routing table structure
        lms_cur.execute("SELECT TOP 1 * FROM Routing")
        routing_cols = [desc[0] for desc in lms_cur.description]
        print(f"\nRouting table columns ({len(routing_cols)}):")
        for col in routing_cols[:20]:  # Show first 20
            print(f"  {col}")
        
        # Check data for sample charter 001009
        print("\n" + "-"*140)
        print("SAMPLE ROUTING DATA FOR 001009:")
        print("-"*140)
        
        lms_cur.execute("""
            SELECT 
                Reserve_No, 
                Type, 
                [Order], 
                Time, 
                Line1, 
                RouteId,
                POIName,
                Notes
            FROM Routing 
            WHERE Reserve_No = '001009'
            ORDER BY [Order]
        """)
        
        routes = lms_cur.fetchall()
        if routes:
            print(f"\nFound {len(routes)} routing records for 001009:")
            for reserve_no, rtype, order, time, line1, route_id, poi, notes in routes:
                type_label = "PICKUP" if rtype == 'P' else "DROPOFF"
                print(f"\n  Order {order} ({type_label}, RouteID {route_id}):")
                print(f"    Time: {time}")
                print(f"    Address: {line1[:80] if line1 else 'N/A'}")
                if poi:
                    print(f"    POI: {poi[:80]}")
                if notes:
                    print(f"    Notes: {notes[:80]}")
        else:
            print("No routing data found for 001009")
        
        # Count total routing data
        lms_cur.execute("SELECT COUNT(*) FROM Routing")
        total_routing = lms_cur.fetchone()[0]
        print(f"\n\nTotal routing records: {total_routing:,}")
        
    except Exception as e:
        if "Routing" in str(e):
            print(f"\n❌ Routing table not found: {e}")
        else:
            raise
    
    lms_conn.close()
    pg_conn.close()
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
