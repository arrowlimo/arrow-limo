#!/usr/bin/env python3
"""Copy vehicles table from local to Neon, matching columns."""
import psycopg2
import json

LOCAL_CONN_STRING = "dbname=almsdata host=localhost user=postgres password=***REDACTED***"
NEON_CONN_STRING = "dbname=neondb host=ep-curly-dream-afnuyxfx-pooler.c-2.us-west-2.aws.neon.tech user=neondb_owner password=npg_89MbcFmZwUWo sslmode=require"

JSON_COLUMNS = {'fuel_efficiency_data', 'maintenance_schedule', 'service_history', 'parts_replacement_history'}

try:
    print("Connecting to local...")
    local_conn = psycopg2.connect(LOCAL_CONN_STRING)
    local_cur = local_conn.cursor()
    
    # Get all local columns
    local_cur.execute("""
        SELECT column_name FROM information_schema.columns 
        WHERE table_name='vehicles' 
        ORDER BY ordinal_position
    """)
    all_local_cols = [row[0] for row in local_cur.fetchall()]
    
    # Get Neon columns
    neon_conn_temp = psycopg2.connect(NEON_CONN_STRING)
    neon_cur_temp = neon_conn_temp.cursor()
    neon_cur_temp.execute("""
        SELECT column_name FROM information_schema.columns 
        WHERE table_name='vehicles' 
        ORDER BY ordinal_position
    """)
    neon_cols = set(row[0] for row in neon_cur_temp.fetchall())
    neon_cur_temp.close()
    neon_conn_temp.close()
    
    # Filter to only matching columns
    matching_cols = [col for col in all_local_cols if col in neon_cols]
    col_indices = {col: i for i, col in enumerate(all_local_cols)}
    matching_indices = [col_indices[col] for col in matching_cols]
    
    print(f"Local columns: {len(all_local_cols)}")
    print(f"Neon columns: {len(neon_cols)}")
    print(f"Matching columns: {len(matching_cols)}\n")
    
    # Fetch all vehicles
    local_cur.execute("SELECT * FROM vehicles ORDER BY vehicle_id")
    vehicles = local_cur.fetchall()
    print(f"Found {len(vehicles)} vehicles")
    
    # Extract and convert matching columns only
    vehicles_json = []
    for vehicle in vehicles:
        vehicle_list = [vehicle[i] for i in matching_indices]
        for i, col in enumerate(matching_cols):
            val = vehicle_list[i]
            if col in JSON_COLUMNS and val is not None and not isinstance(val, str):
                vehicle_list[i] = json.dumps(val)
        vehicles_json.append(tuple(vehicle_list))
    
    local_cur.close()
    local_conn.close()
    print(f"✅ Extracted and converted {len(vehicles_json)} vehicles\n")
    
    # Connect to Neon
    print("Connecting to Neon...")
    neon_conn = psycopg2.connect(NEON_CONN_STRING)
    neon_cur = neon_conn.cursor()
    
    # Check current
    neon_cur.execute("SELECT COUNT(*) FROM vehicles")
    current = neon_cur.fetchone()[0]
    print(f"Current Neon vehicles: {current}")
    
    if current > 0:
        neon_cur.execute("DELETE FROM vehicles")
        neon_conn.commit()
        print("Cleared existing vehicles\n")
    
    # Insert
    print(f"Inserting {len(vehicles_json)} vehicles...")
    columns_str = ', '.join(matching_cols)
    placeholders = ', '.join(['%s'] * len(matching_cols))
    insert_sql = f"INSERT INTO vehicles ({columns_str}) VALUES ({placeholders})"
    
    inserted = 0
    for vehicle in vehicles_json:
        neon_cur.execute(insert_sql, vehicle)
        inserted += 1
        if inserted % 5 == 0:
            neon_conn.commit()
            print(f"  {inserted}/{len(vehicles_json)}")
    
    neon_conn.commit()
    print(f"\n✅ Inserted all {len(vehicles_json)} vehicles")
    
    # Verify
    neon_cur.execute("SELECT COUNT(*) FROM vehicles")
    final = neon_cur.fetchone()[0]
    print(f"Final Neon vehicles: {final}\n")
    
    if final == len(vehicles):
        print("✅ SUCCESS: All vehicles restored to Neon!")
    else:
        print(f"⚠️  Mismatch: inserted {len(vehicles)}, got {final}")
    
    neon_cur.close()
    neon_conn.close()

except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()
