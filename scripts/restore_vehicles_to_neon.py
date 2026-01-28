#!/usr/bin/env python3
"""Copy vehicles table from local almsdata to Neon."""
import psycopg2

LOCAL_CONN = {
    'host': 'localhost',
    'dbname': 'almsdata',
    'user': 'postgres',
    'password': '***REMOVED***',
}

NEON_CONN = {
    'host': 'ep-curly-dream-afnuyxfx-pooler.c-2.us-west-2.aws.neon.tech',
    'dbname': 'neondb',
    'user': 'neondb_owner',
    'password': '***REMOVED***',
    'sslmode': 'require',
}

try:
    # Connect to local
    print("Connecting to local almsdata...")
    local_conn = psycopg2.connect(**LOCAL_CONN)
    local_cur = local_conn.cursor()
    
    # Get column names first
    local_cur.execute("""
        SELECT column_name FROM information_schema.columns 
        WHERE table_name='vehicles' 
        ORDER BY ordinal_position
    """)
    columns = [row[0] for row in local_cur.fetchall()]
    print(f"Columns: {', '.join(columns[:10])}... ({len(columns)} total)")
    
    # Get vehicles from local
    local_cur.execute("SELECT * FROM vehicles ORDER BY vehicle_id")
    vehicles = local_cur.fetchall()
    print(f"Found {len(vehicles)} vehicles in local database")
    print(f"First vehicle type: {type(vehicles[0])}")
    print(f"First vehicle sample: {str(vehicles[0])[:100]}")
    
    if len(vehicles) == 0:
        print("❌ No vehicles found in local database!")
        local_cur.close()
        local_conn.close()
        exit(1)
    
    local_cur.close()
    local_conn.close()
    
    # Connect to Neon
    print("\nConnecting to Neon...")
    neon_conn = psycopg2.connect(**NEON_CONN)
    neon_cur = neon_conn.cursor()
    
    # Check current Neon vehicles count
    neon_cur.execute("SELECT COUNT(*) FROM vehicles")
    current_count = neon_cur.fetchone()[0]
    print(f"Current Neon vehicles: {current_count}")
    
    # Clear existing (if any)
    if current_count > 0:
        print(f"Clearing {current_count} existing vehicles from Neon...")
        neon_cur.execute("DELETE FROM vehicles")
        neon_conn.commit()
    
    # Insert vehicles
    print(f"\nInserting {len(vehicles)} vehicles into Neon...")
    columns_str = ', '.join(columns)
    placeholders = ', '.join(['%s'] * len(columns))
    insert_sql = f"INSERT INTO vehicles ({columns_str}) VALUES ({placeholders})"
    
    for vehicle in vehicles:
        neon_cur.execute(insert_sql, vehicle)
    
    neon_conn.commit()
    print(f"✅ Inserted {len(vehicles)} vehicles")
    
    # Verify
    neon_cur.execute("SELECT COUNT(*) FROM vehicles")
    final_count = neon_cur.fetchone()[0]
    print(f"Final Neon vehicles: {final_count}")
    
    if final_count == len(vehicles):
        print(f"\n✅ SUCCESS: All {final_count} vehicles restored to Neon")
    else:
        print(f"\n❌ MISMATCH: Expected {len(vehicles)}, got {final_count}")
    
    neon_cur.close()
    neon_conn.close()

except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
