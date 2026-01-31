#!/usr/bin/env python
"""Check mileage tracking system - logs, tables, and data completeness."""

import psycopg2
import os

conn = psycopg2.connect(
    host=os.getenv('DB_HOST', 'localhost'),
    dbname=os.getenv('DB_NAME', 'almsdata'),
    user=os.getenv('DB_USER', 'postgres'),
    password=os.getenv('DB_PASSWORD', '***REDACTED***')
)
cur = conn.cursor()

print("\n" + "=" * 120)
print("MILEAGE TRACKING SYSTEM ANALYSIS")
print("=" * 120)

# Check for mileage/odometer related tables
print("\n1. MILEAGE-RELATED TABLES")
print("-" * 120)

cur.execute("""
    SELECT table_name 
    FROM information_schema.tables 
    WHERE table_schema = 'public' 
    AND (table_name LIKE '%mileage%' 
         OR table_name LIKE '%odometer%' 
         OR table_name LIKE '%mile%'
         OR table_name LIKE '%kilometer%'
         OR table_name LIKE '%km%')
    ORDER BY table_name
""")
mileage_tables = cur.fetchall()

if mileage_tables:
    print("Found mileage-related tables:")
    for (table,) in mileage_tables:
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        count = cur.fetchone()[0]
        print(f"  - {table}: {count:,} records")
else:
    print("⚠️  NO dedicated mileage tracking tables found!")

# Check charters table for mileage fields
print("\n2. CHARTERS TABLE - MILEAGE FIELDS")
print("-" * 120)

cur.execute("""
    SELECT column_name, data_type, is_nullable
    FROM information_schema.columns
    WHERE table_schema = 'public'
    AND table_name = 'charters'
    AND (column_name LIKE '%odometer%' 
         OR column_name LIKE '%mileage%'
         OR column_name LIKE '%mile%'
         OR column_name LIKE '%km%')
    ORDER BY ordinal_position
""")
charter_mileage_cols = cur.fetchall()

if charter_mileage_cols:
    print("Mileage columns in charters table:")
    for col_name, data_type, nullable in charter_mileage_cols:
        print(f"  - {col_name}: {data_type} (nullable: {nullable})")
        
        # Check how many records have data
        cur.execute(f"""
            SELECT 
                COUNT(*) as total,
                COUNT({col_name}) as populated,
                COUNT(*) - COUNT({col_name}) as null_count
            FROM charters
        """)
        total, populated, nulls = cur.fetchone()
        pct = (populated / total * 100) if total > 0 else 0
        print(f"    Total: {total:,} | Populated: {populated:,} ({pct:.1f}%) | Null: {nulls:,}")
else:
    print("⚠️  NO mileage columns found in charters table!")

# Check vehicles table for current odometer data
print("\n3. VEHICLES TABLE - ODOMETER STATUS")
print("-" * 120)

cur.execute("""
    SELECT 
        COUNT(*) as total_vehicles,
        COUNT(odometer) as has_odometer,
        COUNT(current_mileage) as has_current_mileage,
        COUNT(CASE WHEN odometer IS NOT NULL AND current_mileage IS NOT NULL THEN 1 END) as has_both,
        COUNT(CASE WHEN odometer IS NULL AND current_mileage IS NULL THEN 1 END) as has_neither,
        COUNT(CASE WHEN odometer IS NOT NULL AND current_mileage IS NULL THEN 1 END) as odometer_only,
        COUNT(CASE WHEN odometer IS NULL AND current_mileage IS NOT NULL THEN 1 END) as current_only
    FROM vehicles
""")
total, has_odo, has_curr, has_both, has_neither, odo_only, curr_only = cur.fetchone()

print(f"Total vehicles: {total}")
print(f"Has odometer value: {has_odo} ({has_odo/total*100:.1f}%)")
print(f"Has current_mileage value: {has_curr} ({has_curr/total*100:.1f}%)")
print(f"Has BOTH values: {has_both} ({has_both/total*100:.1f}%)")
print(f"Has NEITHER value: {has_neither} ({has_neither/total*100:.1f}%)")
print(f"Odometer only: {odo_only}")
print(f"Current_mileage only: {curr_only}")

# Compare odometer vs current_mileage values
cur.execute("""
    SELECT 
        vehicle_id,
        unit_number,
        make,
        model,
        year,
        odometer,
        current_mileage,
        CASE 
            WHEN odometer = current_mileage THEN 'SAME'
            WHEN odometer IS NULL AND current_mileage IS NOT NULL THEN 'CURR_ONLY'
            WHEN odometer IS NOT NULL AND current_mileage IS NULL THEN 'ODO_ONLY'
            WHEN odometer != current_mileage THEN 'DIFFERENT'
            ELSE 'BOTH_NULL'
        END as comparison
    FROM vehicles
    WHERE odometer IS NOT NULL OR current_mileage IS NOT NULL
    ORDER BY vehicle_id
""")
vehicles_with_mileage = cur.fetchall()

if vehicles_with_mileage:
    print(f"\n{len(vehicles_with_mileage)} vehicles have mileage data:")
    print(f"\n{'ID':<6} {'Unit#':<12} {'Vehicle':<30} {'Odometer':<12} {'Current':<12} {'Status':<12}")
    print("-" * 120)
    for vid, unit, make, model, year, odo, curr, comp in vehicles_with_mileage:
        vehicle = f"{make or ''} {model or ''} {year or ''}".strip()[:29]
        print(f"{vid:<6} {unit or 'N/A':<12} {vehicle:<30} {odo or 'NULL':<12} {curr or 'NULL':<12} {comp:<12}")

# Check for HOS (Hours of Service) tables
print("\n4. HOS (HOURS OF SERVICE) TRACKING")
print("-" * 120)

cur.execute("""
    SELECT table_name 
    FROM information_schema.tables 
    WHERE table_schema = 'public' 
    AND (table_name LIKE '%hos%' 
         OR table_name LIKE '%hours%'
         OR table_name LIKE '%duty%'
         OR table_name LIKE '%shift%')
    ORDER BY table_name
""")
hos_tables = cur.fetchall()

if hos_tables:
    print("Found HOS/Hours tracking tables:")
    for (table,) in hos_tables:
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        count = cur.fetchone()[0]
        print(f"  - {table}: {count:,} records")
else:
    print("⚠️  NO HOS tracking tables found!")

# Check for maintenance/service tables
print("\n5. MAINTENANCE/SERVICE TRACKING")
print("-" * 120)

cur.execute("""
    SELECT table_name 
    FROM information_schema.tables 
    WHERE table_schema = 'public' 
    AND (table_name LIKE '%maintenance%' 
         OR table_name LIKE '%service%'
         OR table_name LIKE '%repair%'
         OR table_name LIKE '%cvip%'
         OR table_name LIKE '%inspection%')
    ORDER BY table_name
""")
maintenance_tables = cur.fetchall()

if maintenance_tables:
    print("Found maintenance/service tracking tables:")
    for (table,) in maintenance_tables:
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        count = cur.fetchone()[0]
        print(f"  - {table}: {count:,} records")
else:
    print("⚠️  NO maintenance tracking tables found!")

# Recommendations
print("\n" + "=" * 120)
print("RECOMMENDATIONS")
print("=" * 120)

print("\n❌ CRITICAL MISSING COMPONENTS:")

missing = []

if not mileage_tables:
    missing.append("• Mileage log table (per charter, per vehicle)")
    
if not charter_mileage_cols:
    missing.append("• Charter mileage fields (odometer_start, odometer_end, total_kms)")
    
if not hos_tables:
    missing.append("• HOS (Hours of Service) log table")
    
if not maintenance_tables:
    missing.append("• Maintenance/service log table with odometer readings")

if curr_only > 0 or has_both > 0:
    missing.append(f"• Remove redundant current_mileage column ({curr_only + has_both} vehicles affected)")

for item in missing:
    print(item)

print("\n✅ RECOMMENDED SCHEMA ADDITIONS:")
print("""
1. CREATE TABLE vehicle_mileage_log (
    log_id SERIAL PRIMARY KEY,
    vehicle_id INTEGER REFERENCES vehicles(vehicle_id),
    charter_id INTEGER REFERENCES charters(charter_id),
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    odometer_reading INTEGER NOT NULL,
    odometer_type VARCHAR(2) DEFAULT 'km',
    recorded_by VARCHAR(100),
    notes TEXT
);

2. ALTER TABLE charters ADD COLUMN IF NOT EXISTS odometer_start INTEGER;
   ALTER TABLE charters ADD COLUMN IF NOT EXISTS odometer_end INTEGER;
   ALTER TABLE charters ADD COLUMN IF NOT EXISTS total_kms INTEGER;

3. CREATE TABLE vehicle_maintenance_log (
    maintenance_id SERIAL PRIMARY KEY,
    vehicle_id INTEGER REFERENCES vehicles(vehicle_id),
    service_date DATE NOT NULL,
    service_type VARCHAR(100),
    odometer_at_service INTEGER,
    description TEXT,
    cost DECIMAL(10,2),
    vendor_name VARCHAR(200),
    receipt_id INTEGER REFERENCES receipts(receipt_id),
    next_service_due_at INTEGER,
    next_service_due_date DATE
);

4. CREATE TABLE driver_hos_log (
    hos_id SERIAL PRIMARY KEY,
    employee_id INTEGER REFERENCES employees(employee_id),
    charter_id INTEGER REFERENCES charters(charter_id),
    vehicle_id INTEGER REFERENCES vehicles(vehicle_id),
    shift_start TIMESTAMP NOT NULL,
    shift_end TIMESTAMP,
    duty_status VARCHAR(50),
    odometer_start INTEGER,
    odometer_end INTEGER,
    location_start VARCHAR(200),
    location_end VARCHAR(200),
    notes TEXT
);

5. ALTER TABLE vehicles DROP COLUMN IF EXISTS current_mileage;
   -- Keep only 'odometer' as the primary field
""")

print("\n" + "=" * 120)

cur.close()
conn.close()
