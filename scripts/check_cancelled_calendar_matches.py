#!/usr/bin/env python3
"""Check how many cancelled charters have driver assignments from calendar"""
import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REMOVED***'
)
cur = conn.cursor()

print("=" * 70)
print("CANCELLED CHARTERS - CALENDAR DRIVER ASSIGNMENT ANALYSIS")
print("=" * 70)

# Total cancelled
cur.execute("SELECT COUNT(*) FROM charters WHERE cancelled = true")
total_cancelled = cur.fetchone()[0]

# Cancelled with any driver assigned
cur.execute("SELECT COUNT(*) FROM charters WHERE cancelled = true AND assigned_driver_id IS NOT NULL")
cancelled_with_driver = cur.fetchone()[0]

# Cancelled with driver from calendar (just applied)
cur.execute("SELECT COUNT(*) FROM charters WHERE cancelled = true AND driver_notes LIKE '%Driver assigned from calendar%'")
cancelled_from_calendar = cur.fetchone()[0]

print(f"\n📊 CANCELLED CHARTERS SUMMARY:")
print(f"   Total cancelled charters: {total_cancelled:,}")
print(f"   With driver assigned: {cancelled_with_driver:,} ({cancelled_with_driver/total_cancelled*100:.1f}%)")
print(f"   Driver from calendar import: {cancelled_from_calendar:,}")

# Sample cancelled charters with calendar drivers
print(f"\n🔍 SAMPLE CANCELLED CHARTERS WITH CALENDAR DRIVERS:")
cur.execute("""
    SELECT reserve_number, charter_date, assigned_driver_id, 
           LEFT(driver_notes, 100) as notes_preview
    FROM charters 
    WHERE cancelled = true 
    AND driver_notes LIKE '%Driver assigned from calendar%'
    ORDER BY charter_date DESC
    LIMIT 10
""")

rows = cur.fetchall()
for reserve, date, driver_id, notes in rows:
    print(f"   {reserve} ({date}): Driver ID {driver_id}")
    print(f"      Notes: {notes}...")

# Breakdown by status
print(f"\n📋 CANCELLED CHARTERS BY STATUS:")
cur.execute("""
    SELECT status, 
           COUNT(*) as total,
           COUNT(assigned_driver_id) as with_driver
    FROM charters 
    WHERE cancelled = true
    GROUP BY status
    ORDER BY total DESC
""")

rows = cur.fetchall()
for status, total, with_driver in rows:
    pct = (with_driver/total*100) if total > 0 else 0
    print(f"   {status or '(null)'}: {total:,} total, {with_driver:,} with driver ({pct:.1f}%)")

cur.close()
conn.close()
