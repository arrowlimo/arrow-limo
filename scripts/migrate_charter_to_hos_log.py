#!/usr/bin/env python
"""Migrate charter assignments to driver HOS log."""

import psycopg2
import os
from datetime import datetime, timedelta

conn = psycopg2.connect(
    host=os.getenv('DB_HOST', 'localhost'),
    dbname=os.getenv('DB_NAME', 'almsdata'),
    user=os.getenv('DB_USER', 'postgres'),
    password=os.getenv('DB_PASSWORD', '***REDACTED***')
)
cur = conn.cursor()

print("\n" + "=" * 100)
print("MIGRATING CHARTER ASSIGNMENTS TO HOS LOG")
print("=" * 100)

# Get charters with driver assignments
print("\nFinding charters with driver assignments...")
cur.execute("""
    SELECT 
        charter_id,
        assigned_driver_id,
        vehicle_id,
        charter_date,
        actual_start_time,
        actual_end_time,
        pickup_address,
        dropoff_address,
        odometer_start,
        odometer_end,
        total_kms,
        driver_hours_worked
    FROM charters
    WHERE assigned_driver_id IS NOT NULL
    AND charter_date IS NOT NULL
    ORDER BY charter_date, actual_start_time
""")

charters = cur.fetchall()
print(f"Found {len(charters):,} charters with driver assignments")

if not charters:
    print("No charters to migrate")
    cur.close()
    conn.close()
    exit(0)

# Insert HOS entries
print("\nCreating HOS log entries...")
inserted = 0
skipped = 0

for charter_id, driver_id, vehicle_id, charter_date, start_time, end_time, pickup, dropoff, odo_start, odo_end, total_kms, hours_worked in charters:
    
    # Use actual times if available, otherwise estimate from charter_date
    if start_time:
        shift_start = start_time
    else:
        shift_start = f"{charter_date} 08:00:00"
    
    if end_time:
        shift_end = end_time
    elif start_time and hours_worked:
        shift_end = f"{start_time}::timestamp + interval '{hours_worked} hours'"
    else:
        shift_end = f"{charter_date} 12:00:00"  # Default 4 hour estimate
    
    # Calculate hours if not provided
    if hours_worked:
        hours_driven = float(hours_worked)
        hours_on_duty = float(hours_worked)
    else:
        hours_driven = 4.0  # Default estimate
        hours_on_duty = 4.0
    
    # Calculate total_kms if available
    kms = int(total_kms) if total_kms else (int(odo_end - odo_start) if odo_end and odo_start else None)
    
    try:
        cur.execute(f"""
            INSERT INTO driver_hos_log 
            (employee_id, charter_id, vehicle_id, shift_date, shift_start, shift_end,
             duty_status, odometer_start, odometer_end, total_kms,
             location_start, location_end, hours_driven, hours_on_duty)
            VALUES (
                %s, %s, %s, %s, {shift_start}, {shift_end},
                'driving', %s, %s, %s,
                %s, %s, %s, %s
            )
            ON CONFLICT DO NOTHING
        """, (
            driver_id, charter_id, vehicle_id, charter_date,
            int(odo_start) if odo_start else None,
            int(odo_end) if odo_end else None,
            kms,
            pickup, dropoff, hours_driven, hours_on_duty
        ))
        
        if cur.rowcount > 0:
            inserted += 1
        else:
            skipped += 1
            
    except Exception as e:
        print(f"Error on charter {charter_id}: {e}")
        skipped += 1

print(f"✅ Inserted {inserted:,} HOS entries")
print(f"⚠️  Skipped {skipped:,} entries (duplicates or errors)")

conn.commit()

# Verify migration
print("\n" + "=" * 100)
print("VERIFICATION")
print("=" * 100)

cur.execute("SELECT COUNT(*) FROM driver_hos_log")
total_entries = cur.fetchone()[0]
print(f"\nTotal HOS log entries: {total_entries:,}")

cur.execute("""
    SELECT duty_status, COUNT(*) 
    FROM driver_hos_log 
    GROUP BY duty_status
    ORDER BY duty_status
""")
print("\nBy duty status:")
for status, count in cur.fetchall():
    print(f"  {status}: {count:,}")

cur.execute("""
    SELECT 
        e.employee_id,
        e.full_name,
        COUNT(h.hos_id) as shift_count,
        SUM(h.hours_driven) as total_hours_driven,
        SUM(h.total_kms) as total_kms_driven
    FROM employees e
    JOIN driver_hos_log h ON e.employee_id = h.employee_id
    GROUP BY e.employee_id, e.full_name
    ORDER BY COUNT(h.hos_id) DESC
    LIMIT 20
""")

print("\nTop 20 drivers by shift count:")
print(f"{'Driver':<40} {'Shifts':<10} {'Hours':<12} {'KMs':<12}")
print("-" * 100)
for emp_id, name, shift_count, hours, kms in cur.fetchall():
    print(f"{name or f'Driver {emp_id}':<40} {shift_count:<10} {hours or 0:<12.1f} {kms or 0:<12}")

print("\n✅ MIGRATION COMPLETE")

cur.close()
conn.close()
