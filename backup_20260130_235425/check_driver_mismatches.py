#!/usr/bin/env python3
"""Check how many paid charters have driver mismatches between charter and payroll"""
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
print("CHARTER-PAYROLL DRIVER MISMATCH ANALYSIS")
print("=" * 70)

# Charters with payroll where both have driver assignments
cur.execute("""
    SELECT COUNT(*) as total
    FROM charters c
    JOIN driver_payroll dp ON dp.charter_id::integer = c.charter_id
    WHERE (dp.payroll_class = 'WAGE' OR dp.payroll_class IS NULL)
    AND c.assigned_driver_id IS NOT NULL
    AND dp.employee_id IS NOT NULL
""")
total_both = cur.fetchone()['total']

# Driver mismatches
cur.execute("""
    SELECT COUNT(*) as mismatch
    FROM charters c
    JOIN driver_payroll dp ON dp.charter_id::integer = c.charter_id
    WHERE (dp.payroll_class = 'WAGE' OR dp.payroll_class IS NULL)
    AND c.assigned_driver_id IS NOT NULL
    AND dp.employee_id IS NOT NULL
    AND c.assigned_driver_id != dp.employee_id
""")
mismatch_count = cur.fetchone()['mismatch']

# Payroll with NULL employee_id
cur.execute("""
    SELECT COUNT(*) as null_emp
    FROM driver_payroll
    WHERE (payroll_class = 'WAGE' OR payroll_class IS NULL)
    AND employee_id IS NULL
""")
null_emp_count = cur.fetchone()['null_emp']

# Charter with driver but no payroll employee
cur.execute("""
    SELECT COUNT(*) as charter_only
    FROM charters c
    JOIN driver_payroll dp ON dp.charter_id::integer = c.charter_id
    WHERE (dp.payroll_class = 'WAGE' OR dp.payroll_class IS NULL)
    AND c.assigned_driver_id IS NOT NULL
    AND dp.employee_id IS NULL
""")
charter_only = cur.fetchone()['charter_only']

print(f"\n📊 SUMMARY:")
print(f"   Charters with both driver assignments: {total_both:,}")
print(f"   Driver mismatches (different IDs): {mismatch_count:,} ({mismatch_count/total_both*100:.1f}% if total_both > 0 else 0)")
print(f"   Charter has driver, payroll has NULL: {charter_only:,}")
print(f"   Total payroll entries with NULL employee_id: {null_emp_count:,}")

# Sample mismatches
print(f"\n🔍 SAMPLE DRIVER MISMATCHES (First 10):")
cur.execute("""
    SELECT c.reserve_number, c.charter_date,
           c.assigned_driver_id as charter_driver_id,
           e1.full_name as charter_driver_name,
           dp.employee_id as payroll_driver_id,
           e2.full_name as payroll_driver_name,
           dp.gross_pay
    FROM charters c
    JOIN driver_payroll dp ON dp.charter_id::integer = c.charter_id
    LEFT JOIN employees e1 ON c.assigned_driver_id = e1.employee_id
    LEFT JOIN employees e2 ON dp.employee_id = e2.employee_id
    WHERE (dp.payroll_class = 'WAGE' OR dp.payroll_class IS NULL)
    AND c.assigned_driver_id IS NOT NULL
    AND dp.employee_id IS NOT NULL
    AND c.assigned_driver_id != dp.employee_id
    ORDER BY c.charter_date DESC
    LIMIT 10
""")

mismatches = cur.fetchall()
if mismatches:
    for row in mismatches:
        print(f"\n   Charter {row['reserve_number']} ({row['charter_date']}):")
        print(f"      Charter assigned: {row['charter_driver_name']} (ID {row['charter_driver_id']})")
        print(f"      Payroll paid to:  {row['payroll_driver_name']} (ID {row['payroll_driver_id']})")
        print(f"      Amount paid: ${row['gross_pay']}")
else:
    print("   No mismatches found")

# Breakdown by reason
print(f"\n📋 POTENTIAL REASONS FOR MISMATCHES:")
print(f"   1. Scheduled driver changed (replacement/substitution)")
print(f"   2. Calendar shows scheduled, payroll shows actual")
print(f"   3. Second driver/training assignments")
print(f"   4. Data entry errors")

cur.close()
conn.close()
