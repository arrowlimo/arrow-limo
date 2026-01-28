"""
Check for 2012 charters missing driver information.
"""
import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REMOVED***'
)
cur = conn.cursor()

print("=" * 80)
print("2012 CHARTERS - DRIVER INFORMATION COMPLETENESS")
print("=" * 80)

# Total 2012 charters
cur.execute("""
    SELECT COUNT(*) 
    FROM charters 
    WHERE EXTRACT(YEAR FROM charter_date) = 2012
""")
total_2012_charters = cur.fetchone()[0]
print(f"\nTotal 2012 charters: {total_2012_charters}")

# Charters with assigned_driver_id
cur.execute("""
    SELECT COUNT(*) 
    FROM charters 
    WHERE EXTRACT(YEAR FROM charter_date) = 2012
    AND assigned_driver_id IS NOT NULL
""")
with_assigned_driver_id = cur.fetchone()[0]
print(f"With assigned_driver_id: {with_assigned_driver_id} ({with_assigned_driver_id/total_2012_charters*100:.1f}%)")

# Charters with driver_name
cur.execute("""
    SELECT COUNT(*) 
    FROM charters 
    WHERE EXTRACT(YEAR FROM charter_date) = 2012
    AND driver_name IS NOT NULL AND driver_name != ''
""")
with_driver_name = cur.fetchone()[0]
print(f"With driver_name: {with_driver_name} ({with_driver_name/total_2012_charters*100:.1f}%)")

# Charters with employee_id
cur.execute("""
    SELECT COUNT(*) 
    FROM charters 
    WHERE EXTRACT(YEAR FROM charter_date) = 2012
    AND employee_id IS NOT NULL
""")
with_employee_id = cur.fetchone()[0]
print(f"With employee_id: {with_employee_id} ({with_employee_id/total_2012_charters*100:.1f}%)")

# Charters missing ALL driver fields
cur.execute("""
    SELECT COUNT(*) 
    FROM charters 
    WHERE EXTRACT(YEAR FROM charter_date) = 2012
    AND (assigned_driver_id IS NULL OR assigned_driver_id = 0)
    AND (driver_name IS NULL OR driver_name = '')
    AND (employee_id IS NULL OR employee_id = 0)
""")
missing_all = cur.fetchone()[0]
print(f"\nMissing ALL driver fields: {missing_all} ({missing_all/total_2012_charters*100:.1f}%)")

# Sample charters missing driver info
print("\n" + "=" * 80)
print("SAMPLE CHARTERS MISSING DRIVER INFORMATION")
print("=" * 80)

cur.execute("""
    SELECT 
        charter_id,
        reserve_number,
        charter_date,
        client_id,
        total_amount_due,
        status,
        assigned_driver_id,
        driver_name,
        employee_id,
        calculated_hours
    FROM charters 
    WHERE EXTRACT(YEAR FROM charter_date) = 2012
    AND (assigned_driver_id IS NULL OR assigned_driver_id = 0)
    AND (driver_name IS NULL OR driver_name = '')
    AND (employee_id IS NULL OR employee_id = 0)
    ORDER BY charter_date
    LIMIT 10
""")

print(f"\n{'Reserve#':<10} {'Date':<12} {'Client':<8} {'Amount':>10} {'Status':<12} {'Hours':>6}")
print("-" * 80)

for row in cur.fetchall():
    charter_id, reserve, date, client, amount, status, assigned, driver, emp, hours = row
    print(f"{reserve or 'N/A':<10} {str(date):<12} {client or 'N/A':<8} "
          f"${amount or 0:>8,.2f} {status or 'N/A':<12} {hours or 0:>5.1f}")

# Check if these charters are linked to payroll
print("\n" + "=" * 80)
print("PAYROLL LINKAGE FOR CHARTERS MISSING DRIVER INFO")
print("=" * 80)

cur.execute("""
    SELECT COUNT(DISTINCT dp.id) 
    FROM driver_payroll dp
    WHERE dp.year = 2012
    AND dp.reserve_number IN (
        SELECT reserve_number 
        FROM charters 
        WHERE EXTRACT(YEAR FROM charter_date) = 2012
        AND (assigned_driver_id IS NULL OR assigned_driver_id = 0)
        AND (driver_name IS NULL OR driver_name = '')
        AND (employee_id IS NULL OR employee_id = 0)
        AND reserve_number IS NOT NULL
    )
""")
payroll_with_missing_driver = cur.fetchone()[0]
print(f"Payroll records linked to charters missing driver info: {payroll_with_missing_driver}")

# Check if driver info exists in driver_payroll but not in charters
print("\n" + "=" * 80)
print("CAN WE BACKFILL DRIVER INFO FROM PAYROLL?")
print("=" * 80)

cur.execute("""
    SELECT 
        c.reserve_number,
        c.charter_date,
        c.assigned_driver_id as charter_driver,
        e.full_name as payroll_driver,
        dp.employee_id as payroll_emp_id,
        COUNT(dp.id) as payroll_records
    FROM charters c
    LEFT JOIN driver_payroll dp ON c.reserve_number = dp.reserve_number AND dp.year = 2012
    LEFT JOIN employees e ON dp.employee_id = e.employee_id
    WHERE EXTRACT(YEAR FROM c.charter_date) = 2012
    AND (c.assigned_driver_id IS NULL OR c.assigned_driver_id = 0)
    AND (c.driver_name IS NULL OR c.driver_name = '')
    AND (c.employee_id IS NULL OR c.employee_id = 0)
    AND dp.employee_id IS NOT NULL
    GROUP BY c.reserve_number, c.charter_date, c.assigned_driver_id, e.full_name, dp.employee_id
    ORDER BY c.charter_date
    LIMIT 10
""")

rows = cur.fetchall()
if rows:
    print(f"\n{'Reserve#':<10} {'Date':<12} {'Payroll Driver':<25} {'Emp ID':>8} {'Records':>8}")
    print("-" * 80)
    for row in rows:
        reserve, date, charter_driver, payroll_driver, emp_id, records = row
        print(f"{reserve or 'N/A':<10} {str(date):<12} {payroll_driver or 'N/A':<25} "
              f"{emp_id or 0:>8} {records:>8}")
    print(f"\n[OK] Can backfill {len(rows)} charters with driver info from payroll")
else:
    print("\n[FAIL] No driver info available in payroll to backfill charters")

# Summary
print("\n" + "=" * 80)
print("SUMMARY")
print("=" * 80)
print(f"Total 2012 charters: {total_2012_charters}")
print(f"Missing driver info: {missing_all} ({missing_all/total_2012_charters*100:.1f}%)")
print(f"Can backfill from payroll: {len(rows) if rows else 0}")
print(f"\nDriver field population rates:")
print(f"  assigned_driver_id: {with_assigned_driver_id/total_2012_charters*100:.1f}%")
print(f"  driver_name: {with_driver_name/total_2012_charters*100:.1f}%")
print(f"  employee_id: {with_employee_id/total_2012_charters*100:.1f}%")

cur.close()
conn.close()
