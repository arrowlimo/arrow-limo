import psycopg2
import re

conn = psycopg2.connect('host=localhost dbname=almsdata user=postgres password=***REDACTED***')
cur = conn.cursor()

print("\n" + "="*100)
print("ANALYZING NAME DATA FROM QB EMPLOYEES")
print("="*100 + "\n")

# Get QB employees with their names
cur.execute("""
    SELECT employee_id, employee_number, full_name, first_name, last_name
    FROM employees
    WHERE employee_number LIKE '8%-%' 
       OR employee_number LIKE '%-%-%'
       OR LENGTH(employee_number) > 15
    ORDER BY full_name
""")

qb_employees = cur.fetchall()

print(f"Found {len(qb_employees)} QB employees with name data:\n")
print(f"{'ID':<6} {'QB_ID':<30} {'full_name':<30} {'first_name':<15} {'last_name':<15}")
print("-"*100)

for emp_id, qb_id, full_name, first_name, last_name in qb_employees[:20]:
    first = first_name or "(none)"
    last = last_name or "(none)"
    print(f"{emp_id:<6} {qb_id:<30} {full_name:<30} {first:<15} {last:<15}")

# Now check if there are matching employees WITHOUT QB IDs
print(f"\n{'='*100}")
print("CHECKING FOR MATCHING EMPLOYEES (non-QB records)")
print("="*100 + "\n")

matches_found = []

for emp_id, qb_id, full_name, first_name, last_name in qb_employees:
    # Look for employees with similar full_name but different employee_id
    cur.execute("""
        SELECT employee_id, employee_number, full_name, first_name, last_name,
               (SELECT COUNT(*) FROM driver_payroll WHERE employee_id = employees.employee_id) as payroll,
               (SELECT COUNT(*) FROM charters WHERE assigned_driver_id = employees.employee_id) as charters
        FROM employees
        WHERE employee_id != %s
          AND (full_name ILIKE %s 
               OR full_name ILIKE %s
               OR full_name ILIKE %s)
          AND (employee_number NOT LIKE '8%%' OR employee_number IS NULL OR employee_number LIKE 'DR%%' OR employee_number LIKE 'H%%' OR employee_number LIKE 'OF%%')
    """, (emp_id, full_name, f"%{full_name}%", f"{full_name}%"))
    
    matches = cur.fetchall()
    if matches:
        matches_found.append((emp_id, qb_id, full_name, first_name, last_name, matches))

print(f"Found {len(matches_found)} QB employees with potential matches:\n")

for qb_emp_id, qb_id, qb_full, qb_first, qb_last, matches in matches_found[:10]:
    print(f"\nQB Employee ID {qb_emp_id}: {qb_full}")
    print(f"  QB data: first='{qb_first}' last='{qb_last}'")
    for match_id, match_num, match_full, match_first, match_last, pay, chrt in matches:
        print(f"  → Match ID {match_id}: {match_full} | first='{match_first}' last='{match_last}' | {match_num or '(no code)'} | P:{pay} C:{chrt}")

print(f"\n{'='*100}")
print("SAMPLE: First 10 current employees to check name structure")
print("="*100 + "\n")

cur.execute("""
    SELECT employee_id, employee_number, full_name, first_name, last_name
    FROM employees
    WHERE (employee_number LIKE 'DR%' OR employee_number LIKE 'H%' OR employee_number LIKE 'OF%')
    ORDER BY employee_id
    LIMIT 10
""")

current = cur.fetchall()
print(f"{'ID':<6} {'Emp#':<10} {'full_name':<30} {'first_name':<15} {'last_name':<15}")
print("-"*100)
for emp_id, emp_num, full_name, first_name, last_name in current:
    first = first_name or "(none)"
    last = last_name or "(none)"
    print(f"{emp_id:<6} {emp_num:<10} {full_name:<30} {first:<15} {last:<15}")

conn.close()
