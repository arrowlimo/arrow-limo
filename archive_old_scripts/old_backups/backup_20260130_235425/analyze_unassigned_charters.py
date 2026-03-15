#!/usr/bin/env python3
"""Analyze the 820 unassigned charters"""
import psycopg2
from psycopg2.extras import RealDictCursor

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REDACTED***'
)
cur = conn.cursor(cursor_factory=RealDictCursor)

print("=" * 70)
print("ANALYZING UNASSIGNED CHARTERS")
print("=" * 70)

# Get unassigned charters with details
cur.execute("""
    SELECT COUNT(*) as total,
           COUNT(CASE WHEN charter_date IS NULL THEN 1 END) as no_date,
           COUNT(CASE WHEN charter_date IS NOT NULL THEN 1 END) as with_date,
           MIN(charter_date) as earliest,
           MAX(charter_date) as latest
    FROM charters 
    WHERE cancelled = false 
    AND assigned_driver_id IS NULL
""")

summary = cur.fetchone()

print(f"\n📊 SUMMARY:")
print(f"   Total unassigned: {summary['total']:,}")
print(f"   With NULL date: {summary['no_date']:,}")
print(f"   With valid date: {summary['with_date']:,}")
if summary['earliest']:
    print(f"   Date range: {summary['earliest']} to {summary['latest']}")

# Check payroll status
cur.execute("""
    SELECT 
        COUNT(*) as unassigned_count,
        COUNT(CASE WHEN dp.employee_id IS NOT NULL THEN 1 END) as payroll_has_driver,
        COUNT(CASE WHEN dp.employee_id IS NULL THEN 1 END) as payroll_no_driver,
        COUNT(CASE WHEN dp.driver_id IS NULL THEN 1 END) as no_payroll
    FROM charters c
    LEFT JOIN driver_payroll dp ON dp.charter_id::integer = c.charter_id
        AND (dp.payroll_class = 'WAGE' OR dp.payroll_class IS NULL)
    WHERE c.cancelled = false 
    AND c.assigned_driver_id IS NULL
""")

payroll_status = cur.fetchone()

print(f"\n🔍 PAYROLL STATUS:")
print(f"   Have payroll with employee_id: {payroll_status['payroll_has_driver']:,}")
print(f"   Have payroll but employee_id NULL: {payroll_status['payroll_no_driver']:,}")
print(f"   No payroll record: {payroll_status['no_payroll']:,}")

# Sample with dates
print(f"\n📋 SAMPLE UNASSIGNED WITH DATES:")
cur.execute("""
    SELECT c.reserve_number, c.charter_date, c.rate, c.balance,
           dp.gross_pay, e.full_name as paid_driver
    FROM charters c
    LEFT JOIN driver_payroll dp ON dp.charter_id::integer = c.charter_id
        AND (dp.payroll_class = 'WAGE' OR dp.payroll_class IS NULL)
    LEFT JOIN employees e ON e.employee_id = dp.employee_id
    WHERE c.cancelled = false 
    AND c.assigned_driver_id IS NULL
    AND c.charter_date IS NOT NULL
    ORDER BY c.charter_date DESC
    LIMIT 10
""")

for row in cur.fetchall():
    driver_info = f"Driver: {row['paid_driver']}" if row['paid_driver'] else f"Pay: ${row['gross_pay']:.2f}" if row['gross_pay'] else "No payroll"
    print(f"   {row['reserve_number']} ({row['charter_date']}): {driver_info}")

# Check reserve numbers
print(f"\n📋 SAMPLE UNASSIGNED RESERVE NUMBERS:")
cur.execute("""
    SELECT reserve_number, charter_date
    FROM charters 
    WHERE cancelled = false 
    AND assigned_driver_id IS NULL
    ORDER BY 
        CASE WHEN reserve_number ~ '^[0-9]+$' THEN reserve_number::integer ELSE 999999 END DESC
    LIMIT 15
""")

for row in cur.fetchall():
    date_str = str(row['charter_date']) if row['charter_date'] else 'No date'
    print(f"   {row['reserve_number']}: {date_str}")

conn.close()
