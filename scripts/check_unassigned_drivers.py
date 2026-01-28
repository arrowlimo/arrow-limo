#!/usr/bin/env python3
"""Check how many charters don't have drivers assigned"""
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
print("CHARTER DRIVER ASSIGNMENT STATUS")
print("=" * 70)

# Active charters without drivers
cur.execute("""
    SELECT COUNT(*) as unassigned
    FROM charters 
    WHERE cancelled = false 
    AND assigned_driver_id IS NULL
""")
unassigned = cur.fetchone()['unassigned']

# Total active charters
cur.execute("""
    SELECT COUNT(*) as total
    FROM charters 
    WHERE cancelled = false
""")
total = cur.fetchone()['total']

# Charters with drivers
assigned = total - unassigned
assigned_pct = (assigned / total * 100) if total > 0 else 0

print(f"\n📊 SUMMARY:")
print(f"   Total active charters: {total:,}")
print(f"   With driver assigned: {assigned:,} ({assigned_pct:.1f}%)")
print(f"   Without driver: {unassigned:,} ({(unassigned/total*100):.1f}%)")

# Check if they have payroll entries (driver was paid but not assigned)
cur.execute("""
    SELECT COUNT(*) as with_payroll
    FROM charters c
    WHERE c.cancelled = false 
    AND c.assigned_driver_id IS NULL
    AND EXISTS (
        SELECT 1 FROM driver_payroll dp 
        WHERE dp.charter_id::integer = c.charter_id
        AND (dp.payroll_class = 'WAGE' OR dp.payroll_class IS NULL)
    )
""")
with_payroll = cur.fetchone()['with_payroll']

print(f"\n🔍 UNASSIGNED CHARTERS ANALYSIS:")
print(f"   Unassigned but have payroll: {with_payroll:,}")
print(f"   Unassigned with no payroll: {unassigned - with_payroll:,}")

# Sample unassigned charters with payroll (driver paid but not assigned)
if with_payroll > 0:
    print(f"\n📋 SAMPLE UNASSIGNED CHARTERS WITH PAYROLL:")
    cur.execute("""
        SELECT c.charter_id, c.reserve_number, c.charter_date,
               dp.gross_pay, e.full_name as paid_driver
        FROM charters c
        JOIN driver_payroll dp ON dp.charter_id::integer = c.charter_id
        LEFT JOIN employees e ON e.employee_id = dp.employee_id
        WHERE c.cancelled = false 
        AND c.assigned_driver_id IS NULL
        AND (dp.payroll_class = 'WAGE' OR dp.payroll_class IS NULL)
        ORDER BY c.charter_date DESC
        LIMIT 10
    """)
    
    for row in cur.fetchall():
        print(f"   Charter {row['reserve_number']} ({row['charter_date']}): {row['paid_driver']} paid ${row['gross_pay']:.2f}")

conn.close()
