import psycopg2

conn = psycopg2.connect('host=localhost dbname=almsdata user=postgres password=***REDACTED***')
cur = conn.cursor()

cur.execute("""
    SELECT employee_id, employee_number, full_name, first_name, last_name, quickbooks_id,
           (SELECT COUNT(*) FROM driver_payroll WHERE employee_id = employees.employee_id) as payroll,
           (SELECT COUNT(*) FROM charters WHERE assigned_driver_id = employees.employee_id) as charters
    FROM employees
    WHERE full_name ILIKE '%marc%cote%' OR quickbooks_id = '8000001E-1412270372'
""")

rows = cur.fetchall()

print(f"\nFound {len(rows)} record(s) for Marc Cote:\n")

for r in rows:
    print(f"ID {r[0]:4d} | EmpNum: {r[1] or '(none)':10s} | {r[2]:20s} | QB_ID: {r[5] or '(none)':20s} | Payroll: {r[6]:3d} | Charters: {r[7]:4d}")

conn.close()
