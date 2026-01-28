import psycopg2

conn = psycopg2.connect('host=localhost dbname=almsdata user=postgres password=***REMOVED***')
cur = conn.cursor()

# Find employees with QB ID patterns in employee_number field
cur.execute("""
    SELECT employee_id, employee_number, quickbooks_id, full_name,
           (SELECT COUNT(*) FROM driver_payroll WHERE employee_id = employees.employee_id) as payroll,
           (SELECT COUNT(*) FROM charters WHERE assigned_driver_id = employees.employee_id) as charters
    FROM employees
    WHERE employee_number LIKE '8%-%' 
       OR employee_number LIKE '%-%-%'
       OR LENGTH(employee_number) > 15
    ORDER BY employee_id
""")

rows = cur.fetchall()

print(f"\n{'='*100}")
print(f"EMPLOYEES WITH QB IDs IN WRONG FIELD (employee_number)")
print(f"{'='*100}\n")
print(f"Found {len(rows)} employees:\n")

for r in rows:
    emp_id, emp_num, qb_id, name, payroll, charters = r
    print(f"ID {emp_id:4d} | {emp_num:30s} | {name:25s} | P:{payroll:3d} C:{charters:4d}")

print(f"\n{'='*100}")

if rows:
    print(f"\nRECOMMENDATION:")
    print(f"  - These QB IDs should be in 'quickbooks_id' field, not 'employee_number'")
    print(f"  - employee_number should be DR###, H###, or OF### (or NULL)")
    print(f"  - QB IDs are legacy/historical - not used operationally")
    print(f"\nOPTIONS:")
    print(f"  1. Clear these QB IDs from employee_number (set to NULL)")
    print(f"  2. Move QB IDs to quickbooks_id field and assign proper employee_number")
    print(f"  3. Delete these records if they're garbage/duplicates")

conn.close()
