#!/usr/bin/env python3
"""
Analyze vehicle type/capacity/classification columns and current usage.
Identify the multi-dimensional "type" problem.
"""

import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REDACTED***'
)
cur = conn.cursor()

print(f"\n{'='*80}")
print("VEHICLE TYPE MULTI-DIMENSIONAL ANALYSIS")
print(f"{'='*80}\n")

# 1. Find all type/capacity/class columns in vehicles table
print("CURRENT VEHICLES TABLE COLUMNS (type/capacity/class/license related):\n")
cur.execute("""
    SELECT column_name, data_type, character_maximum_length
    FROM information_schema.columns 
    WHERE table_name = 'vehicles' 
      AND (column_name LIKE '%type%' 
        OR column_name LIKE '%capacity%' 
        OR column_name LIKE '%class%'
        OR column_name LIKE '%license%'
        OR column_name LIKE '%passenger%')
    ORDER BY ordinal_position
""")

for row in cur.fetchall():
    col, dtype, maxlen = row
    print(f"  {col:<30} {dtype:<20} {maxlen or ''}")

# 2. Get current vehicle_type values
print(f"\n{'='*80}")
print("CURRENT vehicle_type VALUES (as stored):\n")
cur.execute("""
    SELECT vehicle_type, passenger_capacity, COUNT(*) as count
    FROM vehicles 
    WHERE vehicle_type IS NOT NULL
    GROUP BY vehicle_type, passenger_capacity
    ORDER BY vehicle_type, passenger_capacity
""")

print(f"{'Type':<30} {'Capacity':<10} {'Count'}")
print("-" * 50)
for row in cur.fetchall():
    vtype, capacity, count = row
    print(f"{vtype:<30} {capacity or 'NULL':<10} {count}")

# 3. Get passenger capacity distribution
print(f"\n{'='*80}")
print("PASSENGER CAPACITY DISTRIBUTION:\n")
cur.execute("""
    SELECT passenger_capacity, COUNT(*) as count,
           CASE 
               WHEN passenger_capacity IS NULL THEN 'Unknown'
               WHEN passenger_capacity <= 10 THEN 'Not Commercial Bus (<11 pax)'
               WHEN passenger_capacity BETWEEN 11 AND 23 THEN 'Commercial Bus, Class 4 OK (11-23 pax)'
               WHEN passenger_capacity >= 24 THEN 'Commercial Bus, Class 2 Required (24+ pax)'
           END as regulatory_classification
    FROM vehicles
    GROUP BY passenger_capacity
    ORDER BY passenger_capacity NULLS FIRST
""")

print(f"{'Capacity':<10} {'Count':<8} {'Regulatory Classification'}")
print("-" * 80)
for row in cur.fetchall():
    capacity, count, reg_class = row
    print(f"{str(capacity) if capacity else 'NULL':<10} {count:<8} {reg_class}")

# 4. Show the 5 dimensions we need to separate
print(f"\n{'='*80}")
print("THE 5 DIMENSIONS OF 'TYPE' WE NEED TO SEPARATE:")
print(f"{'='*80}\n")

dimensions = [
    ("1. REGULATORY_CLASS", "Commercial Vehicle Regulation", 
     "bus (11+ pax) vs not_bus (<11 pax)", 
     "Determines if commercial vehicle regs apply"),
    
    ("2. VEHICLE_CATEGORY", "Customer-Facing Type", 
     "sedan, 6-pax SUV, 13-pax SUV, 20-pax party bus, 27-pax limo bus", 
     "What customers see when booking"),
    
    ("3. LICENSE_REQUIREMENT", "Driver Qualification", 
     "Class 2 (24+ pax), Class 4 (11-23 pax), Class 5 (<11 pax)", 
     "License class required to drive"),
    
    ("4. CAPACITY_GROUP", "Vehicle Allocation", 
     "Groups by size for availability lookups",
     "For suggesting 'next size up' if unavailable"),
    
    ("5. HOURS_OF_SERVICE_TYPE", "Driving Hours Regulation",
     "driving_commercial_bus (11+ pax) vs on_duty_non_bus (<11 pax)",
     "How hours are logged for HOS compliance")
]

for name, purpose, values, description in dimensions:
    print(f"{name}")
    print(f"  Purpose: {purpose}")
    print(f"  Values: {values}")
    print(f"  Used for: {description}")
    print()

# 5. Show sample vehicles with current confusion
print(f"\n{'='*80}")
print("SAMPLE VEHICLES SHOWING CURRENT 'TYPE' CONFUSION:")
print(f"{'='*80}\n")

cur.execute("""
    SELECT vehicle_number, vehicle_type, passenger_capacity, make, model
    FROM vehicles
    WHERE vehicle_type IS NOT NULL
    ORDER BY passenger_capacity NULLS FIRST, vehicle_number
    LIMIT 15
""")

print(f"{'Vehicle#':<10} {'Type (current)':<30} {'Pax':<5} {'Make/Model'}")
print("-" * 80)
for row in cur.fetchall():
    vnum, vtype, cap, make, model = row
    print(f"{vnum:<10} {vtype:<30} {cap or '?':<5} {make or '?'} {model or ''}")

print(f"\n{'='*80}")
print("RECOMMENDED SOLUTION:")
print(f"{'='*80}\n")
print("Add 4 new columns to vehicles table:")
print("  1. regulatory_class VARCHAR(20) - 'bus' or 'non_bus' (based on 11+ pax)")
print("  2. license_class_required VARCHAR(10) - '2', '4', or '5'")
print("  3. capacity_group VARCHAR(20) - 'sedan', 'small_suv', 'large_suv', 'small_bus', 'large_bus'")
print("  4. hos_category VARCHAR(30) - 'commercial_bus_driving' or 'on_duty_non_bus'")
print()
print("Keep:")
print("  - vehicle_type (customer-facing description)")
print("  - passenger_capacity (actual number)")
print()
print("Auto-populate new columns based on passenger_capacity thresholds.")

cur.close()
conn.close()
