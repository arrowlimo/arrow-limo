#!/usr/bin/env python3
import psycopg2
import os

conn = psycopg2.connect(
    host=os.environ.get("DB_HOST", "localhost"),
    database=os.environ.get("DB_NAME", "almsdata"),
    user=os.environ.get("DB_USER", "postgres"),
    password=os.environ.get("DB_PASSWORD", "***REMOVED***")
)
cur = conn.cursor()

# Check vehicles table columns
cur.execute("""
    SELECT column_name, data_type 
    FROM information_schema.columns 
    WHERE table_name = 'vehicles' 
    ORDER BY ordinal_position
""")
print("=== VEHICLES TABLE COLUMNS ===")
for col, dtype in cur.fetchall():
    print(f"  {col}: {dtype}")

# Check vehicle_pricing_defaults
cur.execute("""
    SELECT column_name, data_type 
    FROM information_schema.columns 
    WHERE table_name = 'vehicle_pricing_defaults' 
    ORDER BY ordinal_position
""")
print("\n=== VEHICLE_PRICING_DEFAULTS COLUMNS ===")
for col, dtype in cur.fetchall():
    print(f"  {col}: {dtype}")

# Sample vehicle with fleet_number
cur.execute("SELECT fleet_number, vehicle_type FROM vehicles LIMIT 2")
print(f"\n=== SAMPLE VEHICLES ===")
for fleet_num, vtype in cur.fetchall():
    print(f"  fleet_number: {fleet_num}, vehicle_type: {vtype}")

# Check if vehicles has hourly_rate or pricing columns
cur.execute("""
    SELECT column_name FROM information_schema.columns 
    WHERE table_name = 'vehicles' AND column_name LIKE '%rate%' OR column_name LIKE '%price%'
""")
rates = cur.fetchall()
print(f"\n=== PRICING COLUMNS IN VEHICLES ===")
if rates:
    for col, in rates:
        print(f"  {col}")
else:
    print("  NONE - vehicles table has NO pricing columns!")

cur.close()
conn.close()
