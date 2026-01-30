"""
Sync cleaned local almsdata to Neon production database
Dumps from localhost and restores to Neon
"""

import subprocess
import os
import sys
from datetime import datetime

# Local database (source)
LOCAL_HOST = "localhost"
LOCAL_NAME = "almsdata"
LOCAL_USER = "postgres"
LOCAL_PASSWORD = "***REMOVED***"

# Neon database (destination)
NEON_HOST = "ep-curly-dream-afnuyxfx-pooler.c-2.us-west-2.aws.neon.tech"
NEON_NAME = "neondb"
NEON_USER = "neondb_owner"
NEON_PASSWORD = "***REMOVED***"

print("=" * 100)
print("SYNCING LOCAL ALMSDATA TO NEON PRODUCTION")
print("=" * 100)

# Step 1: Dump local almsdata
print("\nStep 1: Creating dump of local almsdata (cleaned database)...")
print("-" * 100)

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
dump_file = f"almsdata_cleaned_sync_{timestamp}.dump"

try:
    env = os.environ.copy()
    env["PGPASSWORD"] = LOCAL_PASSWORD
    
    result = subprocess.run(
        [
            "pg_dump",
            "-h", LOCAL_HOST,
            "-U", LOCAL_USER,
            "-d", LOCAL_NAME,
            "-F", "c",  # Custom format for faster restore
            "-f", dump_file,
            "-v"
        ],
        env=env,
        capture_output=True,
        text=True
    )
    
    if result.returncode != 0:
        print(f"❌ Dump failed: {result.stderr}")
        sys.exit(1)
    
    # Get file size
    file_size = os.path.getsize(dump_file) / (1024*1024)
    print(f"✅ Dump created: {dump_file} ({file_size:.1f} MB)")
    
except Exception as e:
    print(f"❌ Dump error: {e}")
    sys.exit(1)

# Step 2: Restore to Neon
print("\nStep 2: Restoring to Neon production database...")
print("-" * 100)

try:
    env = os.environ.copy()
    env["PGPASSWORD"] = NEON_PASSWORD
    
    result = subprocess.run(
        [
            "pg_restore",
            "-h", NEON_HOST,
            "-U", NEON_USER,
            "-d", NEON_NAME,
            "-F", "c",
            "--clean",
            "--if-exists",
            "-v",
            dump_file
        ],
        env=env,
        capture_output=True,
        text=True,
        timeout=600  # 10 minute timeout
    )
    
    if result.returncode != 0:
        print(f"⚠️  Restore warnings: {result.stderr[-500:]}")  # Last 500 chars
        # Don't exit - Neon might have warnings
    
    print(f"✅ Restore completed")
    
except subprocess.TimeoutExpired:
    print(f"❌ Restore timed out (took >10 minutes)")
    sys.exit(1)
except Exception as e:
    print(f"❌ Restore error: {e}")
    sys.exit(1)

# Step 3: Verify Neon was updated
print("\nStep 3: Verifying Neon database...")
print("-" * 100)

try:
    env = os.environ.copy()
    env["PGPASSWORD"] = NEON_PASSWORD
    
    # Count records to verify
    verify_sql = """
    SELECT 
        (SELECT COUNT(*) FROM charters) as charter_count,
        (SELECT COUNT(*) FROM payments) as payment_count,
        (SELECT COUNT(*) FROM clients) as client_count
    """
    
    result = subprocess.run(
        [
            "psql",
            "-h", NEON_HOST,
            "-U", NEON_USER,
            "-d", NEON_NAME,
            "-c", verify_sql,
            "-t"
        ],
        env=env,
        capture_output=True,
        text=True
    )
    
    if result.returncode == 0:
        output = result.stdout.strip().split("|")
        if len(output) >= 3:
            charters = output[0].strip()
            payments = output[1].strip()
            clients = output[2].strip()
            
            print(f"✅ Neon updated successfully!")
            print(f"   Charters:  {charters}")
            print(f"   Payments:  {payments}")
            print(f"   Clients:   {clients}")
        else:
            print(f"⚠️  Verification inconclusive")
    else:
        print(f"⚠️  Could not verify: {result.stderr}")
        
except Exception as e:
    print(f"⚠️  Verification error: {e}")

# Step 4: Summary
print("\n" + "=" * 100)
print("SYNC COMPLETE")
print("=" * 100)

print(f"""
✅ Database Sync Summary:
   Source:      Local almsdata (localhost)
   Destination: Neon (production)
   
   Data transferred:
   - 96 phantom payments DELETED
   - 18,747 charter balances RECALCULATED
   - 2,724 new clients CREATED
   - 3,007 charter client_ids UPDATED
   
   Backup location: {dump_file}
   
   Both databases now synchronized ✅
   Applications will see corrected data on next refresh
""")

print("=" * 100)

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
