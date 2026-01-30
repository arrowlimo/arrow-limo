#!/usr/bin/env python3
"""Check if unmatched vehicle charters are cancelled."""

import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REDACTED***'
)
cur = conn.cursor()

print(f"\n{'='*80}")
print("UNMATCHED VEHICLE CHARTERS - STATUS ANALYSIS")
print(f"{'='*80}\n")

# Status breakdown
cur.execute("""
    SELECT booking_status, COUNT(*) as count
    FROM charters c
    LEFT JOIN vehicles v ON UPPER(REPLACE(TRIM(c.vehicle), '-', '')) = UPPER(REPLACE(TRIM(v.vehicle_number), '-', ''))
    WHERE c.vehicle IS NOT NULL 
      AND TRIM(c.vehicle) != ''
      AND c.vehicle_id IS NULL 
      AND v.vehicle_id IS NULL
    GROUP BY booking_status
    ORDER BY count DESC
""")

print(f"{'Status':<25} {'Count':<10} {'%'}")
print("-" * 45)
total = 0
statuses = []
for row in cur.fetchall():
    status, count = row
    statuses.append((status, count))
    total += count

for status, count in statuses:
    pct = (count / total * 100) if total > 0 else 0
    print(f"{status or 'NULL':<25} {count:<10} {pct:.1f}%")

print(f"\n{'Total':<25} {total}")

# Show sample of each status with vehicle values
print(f"\n\n{'='*80}")
print("SAMPLE RECORDS BY STATUS")
print(f"{'='*80}\n")

for status, count in statuses:
    cur.execute("""
        SELECT c.charter_id, c.reserve_number, c.vehicle, c.charter_date::date, c.booking_status
        FROM charters c
        LEFT JOIN vehicles v ON UPPER(REPLACE(TRIM(c.vehicle), '-', '')) = UPPER(REPLACE(TRIM(v.vehicle_number), '-', ''))
        WHERE c.vehicle IS NOT NULL 
          AND TRIM(c.vehicle) != ''
          AND c.vehicle_id IS NULL 
          AND v.vehicle_id IS NULL
          AND c.booking_status = %s
        LIMIT 5
    """, (status,))
    
    print(f"Status: {status or 'NULL'} ({count} records)")
    print(f"{'Charter':<10} {'Reserve#':<15} {'Vehicle':<15} {'Date':<12} {'Status'}")
    print("-" * 75)
    for row in cur.fetchall():
        cid, rnum, vehicle, date, status = row
        print(f"{cid:<10} {rnum or 'N/A':<15} {vehicle:<15} {str(date) if date else 'N/A':<12} {status or 'NULL'}")
    print()

# Breakdown by vehicle value for L-21
print(f"\n{'='*80}")
print("L-21 VEHICLE BREAKDOWN BY STATUS")
print(f"{'='*80}\n")

cur.execute("""
    SELECT c.booking_status, COUNT(*) as count
    FROM charters c
    LEFT JOIN vehicles v ON UPPER(REPLACE(TRIM(c.vehicle), '-', '')) = UPPER(REPLACE(TRIM(v.vehicle_number), '-', ''))
    WHERE c.vehicle = 'L-21'
      AND c.vehicle_id IS NULL 
      AND v.vehicle_id IS NULL
    GROUP BY c.booking_status
    ORDER BY count DESC
""")

print(f"{'Status':<25} {'Count'}")
print("-" * 35)
for row in cur.fetchall():
    status, count = row
    print(f"{status or 'NULL':<25} {count}")

cur.close()
conn.close()
