#!/usr/bin/env python
"""Create complete mileage tracking system with all required tables."""

import psycopg2
import os
from datetime import datetime

conn = psycopg2.connect(
    host=os.getenv('DB_HOST', 'localhost'),
    dbname=os.getenv('DB_NAME', 'almsdata'),
    user=os.getenv('DB_USER', 'postgres'),
    password=os.getenv('DB_PASSWORD', '***REMOVED***')
)
cur = conn.cursor()

print("\n" + "=" * 100)
print("CREATING COMPREHENSIVE MILEAGE TRACKING SYSTEM")
print("=" * 100)

# 1. Create vehicle_mileage_log table
print("\n1. Creating vehicle_mileage_log table...")
cur.execute("""
    CREATE TABLE IF NOT EXISTS vehicle_mileage_log (
        log_id SERIAL PRIMARY KEY,
        vehicle_id INTEGER REFERENCES vehicles(vehicle_id),
        charter_id INTEGER REFERENCES charters(charter_id),
        recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        odometer_reading INTEGER NOT NULL,
        odometer_type VARCHAR(2) DEFAULT 'km',
        recorded_by VARCHAR(100),
        reading_type VARCHAR(50), -- 'charter_start', 'charter_end', 'maintenance', 'inspection', 'manual'
        notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
""")
print("✅ vehicle_mileage_log created")

# Create index for fast lookups
cur.execute("""
    CREATE INDEX IF NOT EXISTS idx_mileage_log_vehicle 
    ON vehicle_mileage_log(vehicle_id, recorded_at DESC)
""")
cur.execute("""
    CREATE INDEX IF NOT EXISTS idx_mileage_log_charter 
    ON vehicle_mileage_log(charter_id)
""")
print("✅ Indexes created on vehicle_mileage_log")

# 2. Create driver_hos_log table
print("\n2. Creating driver_hos_log table...")
cur.execute("""
    CREATE TABLE IF NOT EXISTS driver_hos_log (
        hos_id SERIAL PRIMARY KEY,
        employee_id INTEGER REFERENCES employees(employee_id),
        charter_id INTEGER REFERENCES charters(charter_id),
        vehicle_id INTEGER REFERENCES vehicles(vehicle_id),
        shift_date DATE NOT NULL,
        shift_start TIMESTAMP NOT NULL,
        shift_end TIMESTAMP,
        duty_status VARCHAR(50), -- 'on_duty', 'driving', 'off_duty', 'sleeper_berth'
        odometer_start INTEGER,
        odometer_end INTEGER,
        total_kms INTEGER,
        location_start VARCHAR(200),
        location_end VARCHAR(200),
        hours_driven DECIMAL(5,2),
        hours_on_duty DECIMAL(5,2),
        violation_flags TEXT, -- JSON array of any HOS violations
        notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
""")
print("✅ driver_hos_log created")

cur.execute("""
    CREATE INDEX IF NOT EXISTS idx_hos_log_employee 
    ON driver_hos_log(employee_id, shift_date DESC)
""")
cur.execute("""
    CREATE INDEX IF NOT EXISTS idx_hos_log_vehicle 
    ON driver_hos_log(vehicle_id, shift_date DESC)
""")
cur.execute("""
    CREATE INDEX IF NOT EXISTS idx_hos_log_charter 
    ON driver_hos_log(charter_id)
""")
print("✅ Indexes created on driver_hos_log")

# 3. Enhance maintenance_records table if needed
print("\n3. Checking maintenance_records table...")
cur.execute("""
    SELECT column_name 
    FROM information_schema.columns 
    WHERE table_name = 'maintenance_records' 
    AND column_name = 'odometer_reading'
""")
if cur.fetchone():
    print("✅ maintenance_records already has odometer_reading column")
else:
    print("Adding odometer_reading to maintenance_records...")
    cur.execute("""
        ALTER TABLE maintenance_records 
        ADD COLUMN IF NOT EXISTS odometer_reading INTEGER
    """)
    print("✅ Added odometer_reading to maintenance_records")

# Add missing columns if needed
cur.execute("""
    ALTER TABLE maintenance_records 
    ADD COLUMN IF NOT EXISTS next_service_km INTEGER,
    ADD COLUMN IF NOT EXISTS receipt_id INTEGER REFERENCES receipts(receipt_id),
    ADD COLUMN IF NOT EXISTS cost DECIMAL(10,2)
""")
print("✅ Enhanced maintenance_records with additional tracking fields")

# 4. Create vehicle_fuel_log table for detailed fuel tracking
print("\n4. Creating vehicle_fuel_log table...")
cur.execute("""
    CREATE TABLE IF NOT EXISTS vehicle_fuel_log (
        fuel_log_id SERIAL PRIMARY KEY,
        vehicle_id INTEGER REFERENCES vehicles(vehicle_id),
        receipt_id INTEGER REFERENCES receipts(receipt_id),
        recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        odometer_reading INTEGER,
        fuel_type VARCHAR(50),
        liters DECIMAL(8,2),
        amount DECIMAL(10,2),
        price_per_liter DECIMAL(6,3),
        location VARCHAR(200),
        filled_by VARCHAR(100),
        notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
""")
print("✅ vehicle_fuel_log created")

cur.execute("""
    CREATE INDEX IF NOT EXISTS idx_fuel_log_vehicle 
    ON vehicle_fuel_log(vehicle_id, recorded_at DESC)
""")
print("✅ Indexes created on vehicle_fuel_log")

# 5. Ensure charters table has all mileage fields
print("\n5. Ensuring charters table has mileage fields...")
cur.execute("""
    ALTER TABLE charters 
    ADD COLUMN IF NOT EXISTS odometer_start INTEGER,
    ADD COLUMN IF NOT EXISTS odometer_end INTEGER,
    ADD COLUMN IF NOT EXISTS total_kms INTEGER
""")
print("✅ Charters table mileage fields verified")

# 6. Remove redundant current_mileage column from vehicles
print("\n6. Removing redundant current_mileage column from vehicles...")
cur.execute("""
    SELECT column_name 
    FROM information_schema.columns 
    WHERE table_name = 'vehicles' 
    AND column_name = 'current_mileage'
""")
if cur.fetchone():
    cur.execute("ALTER TABLE vehicles DROP COLUMN current_mileage")
    print("✅ Removed redundant current_mileage column")
else:
    print("✅ current_mileage column already removed")

# 7. Create triggers to auto-update vehicle odometer from mileage log
print("\n7. Creating trigger to keep vehicle odometer updated...")
cur.execute("""
    CREATE OR REPLACE FUNCTION update_vehicle_odometer()
    RETURNS TRIGGER AS $$
    BEGIN
        -- Update vehicle's odometer to the latest reading
        UPDATE vehicles 
        SET odometer = NEW.odometer_reading,
            updated_at = CURRENT_TIMESTAMP
        WHERE vehicle_id = NEW.vehicle_id
        AND (odometer IS NULL OR NEW.odometer_reading > odometer);
        
        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
""")

cur.execute("DROP TRIGGER IF EXISTS trg_update_vehicle_odometer ON vehicle_mileage_log")
cur.execute("""
    CREATE TRIGGER trg_update_vehicle_odometer
    AFTER INSERT ON vehicle_mileage_log
    FOR EACH ROW
    EXECUTE FUNCTION update_vehicle_odometer()
""")
print("✅ Trigger created to auto-update vehicle odometer")

# 8. Create view for latest mileage per vehicle
print("\n8. Creating view for latest mileage per vehicle...")
cur.execute("""
    CREATE OR REPLACE VIEW v_vehicle_latest_mileage AS
    WITH latest_readings AS (
        SELECT 
            vehicle_id,
            odometer_reading,
            recorded_at,
            reading_type,
            ROW_NUMBER() OVER (PARTITION BY vehicle_id ORDER BY recorded_at DESC) as rn
        FROM vehicle_mileage_log
    )
    SELECT 
        v.vehicle_id,
        v.unit_number,
        v.make,
        v.model,
        v.year,
        v.vehicle_type,
        v.odometer as vehicle_odometer,
        lr.odometer_reading as latest_logged_mileage,
        lr.recorded_at as last_reading_date,
        lr.reading_type as last_reading_type,
        COALESCE(lr.odometer_reading, v.odometer, 0) as current_mileage
    FROM vehicles v
    LEFT JOIN latest_readings lr ON v.vehicle_id = lr.vehicle_id AND lr.rn = 1
""")
print("✅ View v_vehicle_latest_mileage created")

# 9. Create view for HOS compliance summary
print("\n9. Creating view for HOS compliance summary...")
cur.execute("""
    CREATE OR REPLACE VIEW v_hos_daily_summary AS
    SELECT 
        employee_id,
        shift_date,
        COUNT(*) as shift_count,
        SUM(hours_driven) as total_hours_driven,
        SUM(hours_on_duty) as total_hours_on_duty,
        SUM(total_kms) as total_kms_driven,
        STRING_AGG(DISTINCT violation_flags, '; ') as violations
    FROM driver_hos_log
    GROUP BY employee_id, shift_date
""")
print("✅ View v_hos_daily_summary created")

# 10. Create function to get maintenance due items
print("\n10. Creating function to get vehicles due for maintenance...")
cur.execute("""
    CREATE OR REPLACE FUNCTION get_vehicles_due_for_maintenance(
        p_days_ahead INTEGER DEFAULT 30,
        p_km_threshold INTEGER DEFAULT 1000
    )
    RETURNS TABLE (
        vehicle_id INTEGER,
        vehicle_name TEXT,
        current_km INTEGER,
        last_service_date DATE,
        last_service_km INTEGER,
        next_service_km INTEGER,
        km_until_service INTEGER,
        service_type VARCHAR
    ) AS $$
    BEGIN
        RETURN QUERY
        SELECT 
            v.vehicle_id,
            CONCAT(v.make, ' ', v.model, ' ', v.year) as vehicle_name,
            v.odometer as current_km,
            mr.service_date as last_service_date,
            mr.odometer_reading as last_service_km,
            mr.next_service_km,
            (mr.next_service_km - v.odometer) as km_until_service,
            mr.service_type
        FROM vehicles v
        JOIN maintenance_records mr ON v.vehicle_id = mr.vehicle_id
        WHERE mr.next_service_km IS NOT NULL
        AND v.odometer IS NOT NULL
        AND (mr.next_service_km - v.odometer) <= p_km_threshold
        ORDER BY km_until_service;
    END;
    $$ LANGUAGE plpgsql;
""")
print("✅ Function get_vehicles_due_for_maintenance created")

# Commit all changes
conn.commit()

# 11. Display summary
print("\n" + "=" * 100)
print("SYSTEM CREATED SUCCESSFULLY")
print("=" * 100)

# Check what we created
cur.execute("""
    SELECT table_name, 
           (SELECT COUNT(*) FROM information_schema.columns c 
            WHERE c.table_name = t.table_name AND c.table_schema = 'public') as column_count
    FROM information_schema.tables t
    WHERE table_schema = 'public'
    AND table_name IN ('vehicle_mileage_log', 'driver_hos_log', 'vehicle_fuel_log', 
                       'maintenance_records')
    ORDER BY table_name
""")
tables = cur.fetchall()

print("\nTables created/updated:")
for table_name, col_count in tables:
    cur.execute(f"SELECT COUNT(*) FROM {table_name}")
    row_count = cur.fetchone()[0]
    print(f"  ✅ {table_name}: {col_count} columns, {row_count:,} records")

print("\nViews created:")
print("  ✅ v_vehicle_latest_mileage")
print("  ✅ v_hos_daily_summary")

print("\nFunctions created:")
print("  ✅ get_vehicles_due_for_maintenance()")

print("\nTriggers created:")
print("  ✅ trg_update_vehicle_odometer (auto-updates vehicle.odometer from mileage log)")

print("\n" + "=" * 100)
print("NEXT STEPS:")
print("=" * 100)
print("""
1. Populate vehicle_mileage_log from existing charter data:
   python -X utf8 scripts/migrate_charter_mileage_to_log.py

2. Create HOS entries from charter assignments:
   python -X utf8 scripts/migrate_charter_to_hos_log.py

3. Import fuel receipts to vehicle_fuel_log:
   python -X utf8 scripts/import_fuel_receipts_to_log.py

4. Set up maintenance reminders based on odometer readings:
   python -X utf8 scripts/setup_maintenance_schedule.py
""")

cur.close()
conn.close()
