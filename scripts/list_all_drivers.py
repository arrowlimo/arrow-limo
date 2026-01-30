import psycopg2

conn = psycopg2.connect('host=localhost dbname=almsdata user=postgres password=***REDACTED***')
cur = conn.cursor()

# Get all drivers/chauffeurs
cur.execute("""
    SELECT employee_id, employee_number, full_name, first_name, last_name, position, is_chauffeur,
           (SELECT COUNT(*) FROM driver_payroll WHERE employee_id = employees.employee_id) as payroll,
           (SELECT COUNT(*) FROM charters WHERE assigned_driver_id = employees.employee_id) as charters
    FROM employees
    WHERE is_chauffeur = TRUE
    ORDER BY employee_number NULLS LAST, full_name
""")

drivers = cur.fetchall()

print(f"\n{'='*110}")
print(f"ALL DRIVERS ({len(drivers)} total)")
print(f"{'='*110}\n")

print(f"{'ID':<6} {'Emp#':<12} {'Full Name':<30} {'First':<15} {'Last':<15} {'Payroll':<8} {'Charters':<9}")
print("-"*110)

for emp_id, emp_num, full, first, last, pos, is_chauff, pay, chrt in drivers:
    emp_display = emp_num or "(no code)"
    print(f"{emp_id:<6} {emp_display:<12} {full:<30} {first or '':<15} {last or '':<15} {pay:<8} {chrt:<9}")

# Summary stats
cur.execute("""
    SELECT 
        COUNT(*) as total,
        COUNT(CASE WHEN employee_number LIKE 'DR%' THEN 1 END) as with_dr_code,
        COUNT(CASE WHEN employee_number IS NULL THEN 1 END) as no_code,
        SUM((SELECT COUNT(*) FROM driver_payroll WHERE employee_id = employees.employee_id)) as total_payroll,
        SUM((SELECT COUNT(*) FROM charters WHERE assigned_driver_id = employees.employee_id)) as total_charters
    FROM employees
    WHERE is_chauffeur = TRUE
""")

stats = cur.fetchone()

print(f"\n{'='*110}")
print("SUMMARY:")
print(f"  Total drivers: {stats[0]}")
print(f"  With DR code: {stats[1]}")
print(f"  No employee code: {stats[2]}")
print(f"  Total payroll records: {stats[3]}")
print(f"  Total charter assignments: {stats[4]}")
print(f"{'='*110}\n")

conn.close()
