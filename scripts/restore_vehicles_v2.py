#!/usr/bin/env python3
"""Copy vehicles table from local almsdata to Neon."""
import psycopg2
import json

LOCAL_CONN_STRING = "dbname=almsdata host=localhost user=postgres password=***REMOVED***"
NEON_CONN_STRING = "dbname=neondb host=ep-curly-dream-afnuyxfx-pooler.c-2.us-west-2.aws.neon.tech user=neondb_owner password=***REMOVED*** sslmode=require"

try:
    # Connect to local
    print("Connecting to local almsdata...")
    local_conn = psycopg2.connect(LOCAL_CONN_STRING)
    local_cur = local_conn.cursor()
    
    # Get column names and vehicles
    local_cur.execute("""
        SELECT column_name FROM information_schema.columns 
        WHERE table_name='vehicles' 
        ORDER BY ordinal_position
    """)
    columns = [row[0] for row in local_cur.fetchall()]
    print(f"Found {len(columns)} columns")
    
    local_cur.execute("SELECT * FROM vehicles ORDER BY vehicle_id")
    vehicles = local_cur.fetchall()
    print(f"Found {len(vehicles)} vehicles")
    
    # Verify first row
    print(f"First row type: {type(vehicles[0])}, len: {len(vehicles[0])}, first 3 cols: {vehicles[0][:3]}")
    
    local_cur.close()
    local_conn.close()
    print("Disconnected from local\n")
    
    # Connect to Neon
    print("Connecting to Neon...")
    neon_conn = psycopg2.connect(NEON_CONN_STRING)
    neon_cur = neon_conn.cursor()
    
    # Check current count
    neon_cur.execute("SELECT COUNT(*) FROM vehicles")
    current = neon_cur.fetchone()[0]
    print(f"Current Neon vehicles: {current}")
    
    if current > 0:
        neon_cur.execute("DELETE FROM vehicles")
        neon_conn.commit()
        print(f"Cleared {current} vehicles")
    
    # Insert
    print(f"Inserting {len(vehicles)} vehicles...")
    columns_str = ', '.join(columns)
    placeholders = ', '.join(['%s'] * len(columns))
    insert_sql = f"INSERT INTO vehicles ({columns_str}) VALUES ({placeholders})"
    
    # Try first row
    print(f"Insert SQL: {insert_sql[:100]}...")
    print(f"First row: {str(vehicles[0][:3])}...")
    neon_cur.execute(insert_sql, vehicles[0])
    neon_conn.commit()
    print("✅ First row inserted successfully")
    
    # Insert rest
    for i, vehicle in enumerate(vehicles[1:], 1):
        neon_cur.execute(insert_sql, vehicle)
        if (i + 1) % 5 == 0:
            neon_conn.commit()
            print(f"  Committed {i + 1}/{len(vehicles)}")
    
    neon_conn.commit()
    print(f"✅ All {len(vehicles)} vehicles inserted")
    
    # Verify
    neon_cur.execute("SELECT COUNT(*) FROM vehicles")
    final = neon_cur.fetchone()[0]
    print(f"Final Neon vehicles: {final}")
    
    if final == len(vehicles):
        print(f"\n✅ SUCCESS!")
    
    neon_cur.close()
    neon_conn.close()

except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
