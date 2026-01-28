#!/usr/bin/env python3
"""
Populate vehicles table pricing columns from vehicle_pricing_defaults.
Uses fleet_number → vehicle_type → pricing lookup.
"""
import psycopg2
import os
from decimal import Decimal

conn = psycopg2.connect(
    host=os.environ.get("DB_HOST", "localhost"),
    database=os.environ.get("DB_NAME", "almsdata"),
    user=os.environ.get("DB_USER", "postgres"),
    password=os.environ.get("DB_PASSWORD", "***REMOVED***")
)
cur = conn.cursor()

try:
    # Step 1: Get all vehicles with vehicle_type
    cur.execute("""
        SELECT vehicle_id, fleet_number, vehicle_type
        FROM vehicles
        WHERE vehicle_type IS NOT NULL
        ORDER BY vehicle_id
    """)
    vehicles = cur.fetchall()
    print(f"Found {len(vehicles)} vehicles with vehicle_type")
    
    # Step 2: Get pricing defaults by vehicle_type
    cur.execute("""
        SELECT vehicle_type, hourly_rate, daily_rate, standby_rate, 
               airport_pickup_edmonton, airport_pickup_calgary
        FROM vehicle_pricing_defaults
    """)
    pricing_map = {}
    for row in cur.fetchall():
        vtype, hr, dr, sr, apt_edm, apt_yyc = row
        pricing_map[vtype] = {
            'hourly_rate': hr,
            'daily_rate': dr,
            'standby_rate': sr,
            'airport_pickup_edmonton': apt_edm,
            'airport_pickup_calgary': apt_yyc
        }
    
    print(f"Loaded pricing defaults for {len(pricing_map)} vehicle types")
    
    # Step 3: Update vehicles with pricing
    updated_count = 0
    missing_pricing = []
    
    for vehicle_id, fleet_num, vehicle_type in vehicles:
        if vehicle_type not in pricing_map:
            missing_pricing.append((fleet_num, vehicle_type))
            continue
        
        pricing = pricing_map[vehicle_type]
        
        # Use hourly_rate as default_hourly_price, and airport rates for airport pricing
        cur.execute("""
            UPDATE vehicles
            SET 
                default_hourly_price = %s,
                airport_pickup_price = %s,
                airport_dropoff_price = %s
            WHERE vehicle_id = %s
        """, (
            pricing['hourly_rate'],
            pricing['airport_pickup_edmonton'],
            pricing['airport_pickup_edmonton'],  # Use Edmonton as default for dropoff
            vehicle_id
        ))
        updated_count += 1
    
    conn.commit()
    print(f"\n✅ Updated {updated_count} vehicles with pricing")
    
    if missing_pricing:
        print(f"\n⚠️  {len(missing_pricing)} vehicles have vehicle_type NOT in pricing defaults:")
        for fleet_num, vtype in missing_pricing[:10]:
            print(f"   fleet_number: {fleet_num}, vehicle_type: {vtype}")
    
    # Step 4: Show sample results
    cur.execute("""
        SELECT fleet_number, vehicle_type, default_hourly_price, airport_pickup_price
        FROM vehicles
        WHERE vehicle_type IS NOT NULL AND default_hourly_price IS NOT NULL
        LIMIT 5
    """)
    print(f"\n=== SAMPLE VEHICLES WITH PRICING ===")
    for fleet, vtype, hourly, airport in cur.fetchall():
        print(f"  {fleet}: {vtype}")
        print(f"    hourly: ${hourly}, airport: ${airport}")

except Exception as e:
    conn.rollback()
    print(f"❌ Error: {e}")
finally:
    cur.close()
    conn.close()
