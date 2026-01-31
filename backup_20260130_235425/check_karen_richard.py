import psycopg2

conn = psycopg2.connect('host=localhost dbname=almsdata user=postgres password=***REDACTED***')
cur = conn.cursor()

cur.execute("""
    SELECT employee_id, employee_number, full_name, first_name, last_name, quickbooks_id
    FROM employees
    WHERE full_name ILIKE '%karen%richard%'
""")

rows = cur.fetchall()

print(f"\nKaren Richard record(s):\n")

for r in rows:
    emp_id, emp_num, full, first, last, qb_id = r
    print(f"ID: {emp_id}")
    print(f"  employee_number: {emp_num or '(none)'}")
    print(f"  full_name: \"{full}\"")
    print(f"  first_name: \"{first or ''}\"")
    print(f"  last_name: \"{last or ''}\"")
    print(f"  quickbooks_id: {qb_id or '(none)'}")
    print(f"\n  Issue: Extra period in full_name: \"Karen. Richard\"")
    print(f"  Should be: \"Karen Richard\" (no period)")

print("\nThis is a typo in the original QuickBooks data.")
print("Fix: UPDATE full_name to 'Karen Richard' and regenerate first/last names")

conn.close()
