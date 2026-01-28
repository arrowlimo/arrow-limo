#!/usr/bin/env python
import psycopg2
import os

conn = psycopg2.connect(
    host=os.environ.get('DB_HOST', 'localhost'),
    database=os.environ.get('DB_NAME', 'almsdata'),
    user=os.environ.get('DB_USER', 'postgres'),
    password=os.environ.get('DB_PASSWORD', '***REMOVED***')
)
cur = conn.cursor()

try:
    # Create vehicle_pricing_defaults table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS vehicle_pricing_defaults (
            vehicle_type VARCHAR(100) PRIMARY KEY,
            hourly_rate DECIMAL(10,2),
            hourly_package DECIMAL(10,2),
            daily_rate DECIMAL(10,2),
            standby_rate DECIMAL(10,2),
            airport_pickup_edmonton DECIMAL(10,2),
            airport_pickup_calgary DECIMAL(10,2),
            nrr DECIMAL(10,2),
            fee_1 DECIMAL(10,2),
            fee_2 DECIMAL(10,2),
            fee_3 DECIMAL(10,2),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    print("✅ Table created successfully")
    
    # Get distinct vehicle types from all vehicles
    cur.execute("""
        SELECT DISTINCT vehicle_type 
        FROM vehicles 
        WHERE vehicle_type IS NOT NULL AND vehicle_type != ''
        ORDER BY vehicle_type
    """)
    vehicle_types = [row[0] for row in cur.fetchall()]
    print(f"\n📋 Found {len(vehicle_types)} active vehicle types:")
    for vtype in vehicle_types:
        print(f"  - {vtype}")
    
    # Mapping NRR by vehicle type patterns
    def get_nrr(vtype):
        vt_lower = vtype.lower()
        if '27' in vt_lower or '72' in vt_lower:
            return 600
        elif 'party' in vt_lower or 'shuttle' in vt_lower or 'bus' in vt_lower:
            return 500
        elif 'suv' in vt_lower and 'stretch' in vt_lower:
            return 300
        elif 'suv' in vt_lower:
            return 300
        elif 'sedan' in vt_lower or 'luxury sedan' in vt_lower:
            return 75
        else:
            return 75  # Default
    
    # Insert/update vehicle types with NRR
    print("\n💰 Populating NRR values:")
    for vtype in vehicle_types:
        nrr = get_nrr(vtype)
        cur.execute("""
            INSERT INTO vehicle_pricing_defaults (vehicle_type, nrr)
            VALUES (%s, %s)
            ON CONFLICT (vehicle_type) DO UPDATE
            SET nrr = %s, updated_at = CURRENT_TIMESTAMP
        """, (vtype, nrr, nrr))
        print(f"  {vtype}: ${nrr}")
    
    conn.commit()
    print(f"\n✅ Successfully populated {len(vehicle_types)} vehicle types")
    
    # Show summary
    cur.execute("SELECT vehicle_type, nrr FROM vehicle_pricing_defaults ORDER BY vehicle_type")
    print("\n📊 Final pricing table:")
    for vtype, nrr in cur.fetchall():
        print(f"  {vtype}: NRR=${nrr}")
    
except Exception as e:
    conn.rollback()
    print(f"❌ Error: {e}")
finally:
    conn.close()
