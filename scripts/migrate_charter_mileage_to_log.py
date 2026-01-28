#!/usr/bin/env python
"""Migrate charter mileage data to vehicle_mileage_log."""

import psycopg2
import os

conn = psycopg2.connect(
    host=os.getenv('DB_HOST', 'localhost'),
    dbname=os.getenv('DB_NAME', 'almsdata'),
    user=os.getenv('DB_USER', 'postgres'),
    password=os.getenv('DB_PASSWORD', '***REMOVED***')
)
cur = conn.cursor()

print("\n" + "=" * 100)
print("MIGRATING CHARTER MILEAGE TO VEHICLE_MILEAGE_LOG")
print("=" * 100)

# Get charters with mileage data
print("\nFinding charters with mileage data...")
cur.execute("""
    SELECT 
        charter_id,
        COALESCE(vehicle_id, vehicle_booked_id) as vehicle_id,
        assigned_driver_id,
        charter_date,
        actual_start_time,
        actual_end_time,
        odometer_start,
        odometer_end,
        total_kms,
        vehicle
    FROM charters
    WHERE odometer_start IS NOT NULL 
    AND odometer_end IS NOT NULL
    ORDER BY charter_date, actual_start_time
""")

charters = cur.fetchall()
print(f"Found {len(charters):,} charters with mileage data")

if not charters:
    print("No charters to migrate")
    cur.close()
    conn.close()
    exit(0)

# Count how many have vehicle IDs
with_vehicle = sum(1 for c in charters if c[1] is not None)
without_vehicle = len(charters) - with_vehicle
print(f"  With vehicle_id: {with_vehicle:,}")
print(f"  Without vehicle_id: {without_vehicle:,} (will skip these)")

# Insert start readings
print("\nInserting odometer START readings...")
start_count = 0
skipped_no_vehicle = 0

for charter_id, vehicle_id, driver_id, charter_date, start_time, end_time, odo_start, odo_end, total_kms, vehicle_name in charters:
    if not vehicle_id:
        skipped_no_vehicle += 1
        continue
    # Use actual_start_time if available, otherwise charter_date
    recorded_at = start_time if start_time else charter_date
    
    cur.execute("""
        INSERT INTO vehicle_mileage_log 
        (vehicle_id, charter_id, recorded_at, odometer_reading, reading_type, recorded_by)
        VALUES (%s, %s, %s, %s, 'charter_start', %s)
        ON CONFLICT DO NOTHING
    """, (vehicle_id, charter_id, recorded_at, int(odo_start), f'driver_{driver_id}' if driver_id else 'system'))
    start_count += cur.rowcount

print(f"✅ Inserted {start_count:,} START readings")
if skipped_no_vehicle > 0:
    print(f"⚠️  Skipped {skipped_no_vehicle:,} (no vehicle_id)")

# Insert end readings
print("\nInserting odometer END readings...")
end_count = 0
skipped_no_vehicle = 0

for charter_id, vehicle_id, driver_id, charter_date, start_time, end_time, odo_start, odo_end, total_kms, vehicle_name in charters:
    if not vehicle_id:
        skipped_no_vehicle += 1
        continue
    # Use actual_end_time if available, otherwise charter_date + 4 hours estimate
    if end_time:
        recorded_at = end_time
    elif start_time:
        recorded_at = f"{start_time}::timestamp + interval '4 hours'"
    else:
        recorded_at = f"{charter_date}::timestamp + interval '4 hours'"
    
    cur.execute(f"""
        INSERT INTO vehicle_mileage_log 
        (vehicle_id, charter_id, recorded_at, odometer_reading, reading_type, recorded_by)
        VALUES (%s, %s, {recorded_at}, %s, 'charter_end', %s)
        ON CONFLICT DO NOTHING
    """, (vehicle_id, charter_id, int(odo_end), f'driver_{driver_id}' if driver_id else 'system'))
    end_count += cur.rowcount

print(f"✅ Inserted {end_count:,} END readings")
if skipped_no_vehicle > 0:
    print(f"⚠️  Skipped {skipped_no_vehicle:,} (no vehicle_id)")

conn.commit()

# Verify migration
print("\n" + "=" * 100)
print("VERIFICATION")
print("=" * 100)

cur.execute("SELECT COUNT(*) FROM vehicle_mileage_log")
total_logs = cur.fetchone()[0]
print(f"\nTotal mileage log entries: {total_logs:,}")

cur.execute("""
    SELECT reading_type, COUNT(*) 
    FROM vehicle_mileage_log 
    GROUP BY reading_type
    ORDER BY reading_type
""")
print("\nBy reading type:")
for reading_type, count in cur.fetchall():
    print(f"  {reading_type}: {count:,}")

cur.execute("""
    SELECT v.vehicle_id, v.unit_number, v.make, v.model, v.odometer, COUNT(vml.log_id) as log_entries
    FROM vehicles v
    LEFT JOIN vehicle_mileage_log vml ON v.vehicle_id = vml.vehicle_id
    GROUP BY v.vehicle_id, v.unit_number, v.make, v.model, v.odometer
    HAVING COUNT(vml.log_id) > 0
    ORDER BY COUNT(vml.log_id) DESC
""")

print("\nMileage logs per vehicle:")
print(f"{'Vehicle':<40} {'Odometer':<12} {'Log Entries':<12}")
print("-" * 100)
for vid, unit, make, model, odo, log_count in cur.fetchall():
    vehicle = f"{make or ''} {model or ''} ({unit or f'ID:{vid}'})".strip()[:39]
    print(f"{vehicle:<40} {odo or 'N/A':<12} {log_count:<12}")

print("\n✅ MIGRATION COMPLETE")

cur.close()
conn.close()
