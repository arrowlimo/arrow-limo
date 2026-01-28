import psycopg2
import os

# Local connection
local_conn = psycopg2.connect(
    host=os.environ.get('DB_HOST', 'localhost'),
    database=os.environ.get('DB_NAME', 'almsdata'),
    user=os.environ.get('DB_USER', 'postgres'),
    password=os.environ.get('DB_PASSWORD', '***REMOVED***'),
)

# Neon connection
neon_conn = psycopg2.connect(
    host='ep-curly-dream-afnuyxfx-pooler.c-2.us-west-2.aws.neon.tech',
    database='neondb',
    user='neondb_owner',
    password='***REMOVED***',
    sslmode='require',
)

local_cur = local_conn.cursor()
neon_cur = neon_conn.cursor()

print("Syncing vehicle_pricing_defaults to Neon...")

# Fetch all pricing data from local
local_cur.execute(
    'SELECT vehicle_type, nrr, hourly_rate, daily_rate, standby_rate, '
    'airport_pickup_calgary, airport_pickup_edmonton, hourly_package, fee_1, fee_2, fee_3, created_at, updated_at '
    'FROM vehicle_pricing_defaults ORDER BY vehicle_type'
)
rows = local_cur.fetchall()

# Clear Neon table
neon_cur.execute('DELETE FROM vehicle_pricing_defaults')

# Insert all rows to Neon
insert_sql = (
    'INSERT INTO vehicle_pricing_defaults '
    '(vehicle_type, nrr, hourly_rate, daily_rate, standby_rate, '
    'airport_pickup_calgary, airport_pickup_edmonton, hourly_package, fee_1, fee_2, fee_3, created_at, updated_at) '
    'VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)'
)

for row in rows:
    neon_cur.execute(insert_sql, row)

neon_conn.commit()
print(f"✓ Synced {len(rows)} vehicle pricing rows to Neon")

print("\nSyncing vehicles fleet_number updates to Neon...")

# Get all vehicles with fleet_number from local
local_cur.execute(
    'SELECT vehicle_id, vehicle_number, fleet_number, vehicle_type '
    'FROM vehicles WHERE fleet_number IS NOT NULL ORDER BY vehicle_id'
)
vehicle_rows = local_cur.fetchall()

# Update Neon vehicles table
for vehicle_id, vehicle_number, fleet_number, vehicle_type in vehicle_rows:
    neon_cur.execute(
        'UPDATE vehicles SET fleet_number = %s, vehicle_type = %s WHERE vehicle_id = %s',
        (fleet_number, vehicle_type, vehicle_id)
    )

neon_conn.commit()
print(f"✓ Updated {len(vehicle_rows)} vehicle rows in Neon")

# Verify sync
print("\n--- Verification ---")
neon_cur.execute('SELECT COUNT(*) FROM vehicle_pricing_defaults')
neon_pricing_count = neon_cur.fetchone()[0]
print(f"Neon vehicle_pricing_defaults: {neon_pricing_count} rows")

neon_cur.execute(
    'SELECT COUNT(*) FROM vehicles WHERE fleet_number IS NOT NULL AND fleet_number = vehicle_number'
)
neon_fleet_count = neon_cur.fetchone()[0]
print(f"Neon vehicles with fleet_number synced: {neon_fleet_count} rows")

local_cur.close()
neon_cur.close()
local_conn.close()
neon_conn.close()

print("\n✅ Bidirectional sync complete!")
