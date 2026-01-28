#!/usr/bin/env python3
"""Check if unassigned charters exist in the calendar import"""
import psycopg2
from psycopg2.extras import RealDictCursor

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REMOVED***'
)
cur = conn.cursor(cursor_factory=RealDictCursor)

print("=" * 70)
print("UNASSIGNED CHARTERS vs CALENDAR DATA")
print("=" * 70)

# Get unassigned charters
cur.execute("""
    SELECT COUNT(*) as cnt
    FROM charters 
    WHERE cancelled = false 
    AND assigned_driver_id IS NULL
""")
unassigned_count = cur.fetchone()['cnt']

print(f"\n📊 Unassigned charters: {unassigned_count:,}")

# Sample unassigned reserve numbers
cur.execute("""
    SELECT reserve_number, charter_date
    FROM charters 
    WHERE cancelled = false 
    AND assigned_driver_id IS NULL
    ORDER BY charter_date DESC
    LIMIT 20
""")

samples = cur.fetchall()
print(f"\n📋 Sample unassigned charter reserve numbers:")
for row in samples[:10]:
    print(f"   {row['reserve_number']} ({row['charter_date']})")

# Check if these exist in calendar
reserve_numbers = [row['reserve_number'] for row in samples]
placeholders = ','.join(['%s'] * len(reserve_numbers))

cur.execute(f"""
    SELECT COUNT(*) as cnt
    FROM arrow_calendar
    WHERE reserve_number IN ({placeholders})
""", reserve_numbers)

in_calendar = cur.fetchone()['cnt']

print(f"\n🔍 Of these {len(reserve_numbers)} samples:")
print(f"   Found in calendar: {in_calendar}")
print(f"   Not in calendar: {len(reserve_numbers) - in_calendar}")

# Check calendar entries without driver assignments
cur.execute("""
    SELECT COUNT(*) as cnt
    FROM arrow_calendar ac
    JOIN charters c ON c.reserve_number = ac.reserve_number
    WHERE c.cancelled = false
    AND c.assigned_driver_id IS NULL
    AND ac.driver_names IS NOT NULL
    AND ac.driver_names != ''
""")

calendar_has_driver = cur.fetchone()['cnt']

print(f"\n✓ Charters in calendar WITH driver info but unassigned: {calendar_has_driver:,}")

# Show samples with driver info
if calendar_has_driver > 0:
    print(f"\n📋 SAMPLE - Calendar has driver but charter doesn't:")
    cur.execute("""
        SELECT c.reserve_number, c.charter_date, ac.driver_names
        FROM arrow_calendar ac
        JOIN charters c ON c.reserve_number = ac.reserve_number
        WHERE c.cancelled = false
        AND c.assigned_driver_id IS NULL
        AND ac.driver_names IS NOT NULL
        AND ac.driver_names != ''
        ORDER BY c.charter_date DESC
        LIMIT 10
    """)
    
    for row in cur.fetchall():
        print(f"   {row['reserve_number']} ({row['charter_date']}): {row['driver_names']}")

conn.close()
