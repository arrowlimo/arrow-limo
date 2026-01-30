import psycopg2, os

conn = psycopg2.connect(
    host=os.environ.get('DB_HOST', 'localhost'),
    database=os.environ.get('DB_NAME', 'almsdata'),
    user=os.environ.get('DB_USER', 'postgres'),
    password=os.environ.get('DB_PASSWORD', '***REDACTED***')
)
cur = conn.cursor()

print('='*80)
print('ALL FOREIGN KEY DEPENDENCIES TO employees.employee_id')
print('='*80)
print()

tables_to_check = [
    ('driver_payroll', 'employee_id'),
    ('employee_expenses', 'employee_id'),
    ('charters', 'assigned_driver_id'),
]

for table, col in tables_to_check:
    try:
        cur.execute(f'SELECT COUNT(DISTINCT "{col}") FROM "{table}" WHERE "{col}" IS NOT NULL')
        count = cur.fetchone()[0]
        print(f'{table:30s}.{col:25s} | {count:3d} distinct employee refs')
    except:
        print(f'{table:30s}.{col:25s} | (table not found)')

print()
print('='*80)
print('LEGACY Records WITH Foreign Key References')
print('='*80)
print()

cur.execute('''
    SELECT DISTINCT e.employee_id, e.employee_number, e.full_name,
           CASE WHEN EXISTS (SELECT 1 FROM driver_payroll dp WHERE dp.employee_id = e.employee_id) THEN 'payroll'
                WHEN EXISTS (SELECT 1 FROM charters c WHERE c.assigned_driver_id = e.employee_id) THEN 'charters'
                WHEN EXISTS (SELECT 1 FROM employee_expenses ee WHERE ee.employee_id = e.employee_id) THEN 'expenses'
                ELSE 'unknown'
           END as ref_type
    FROM employees e
    WHERE e.employee_number LIKE 'LEGACY-%'
      AND (
        EXISTS (SELECT 1 FROM driver_payroll dp WHERE dp.employee_id = e.employee_id)
        OR EXISTS (SELECT 1 FROM charters c WHERE c.assigned_driver_id = e.employee_id)
        OR EXISTS (SELECT 1 FROM employee_expenses ee WHERE ee.employee_id = e.employee_id)
      )
    ORDER BY e.employee_id
''')

unsafe = cur.fetchall()
print(f'Found {len(unsafe)} LEGACY records WITH foreign key refs (cannot delete without handling):')
print()
if unsafe:
    for emp_id, emp_num, name, ref_type in unsafe[:30]:
        print(f'  ID={emp_id:3d} | {emp_num:20s} | {name:30s} | ref: {ref_type}')

print()
print('='*80)
print('SAFE TO DELETE: LEGACY records with NO foreign key refs')
print('='*80)
print()

cur.execute('''
    SELECT COUNT(*)
    FROM employees e
    WHERE e.employee_number LIKE 'LEGACY-%'
      AND NOT EXISTS (SELECT 1 FROM driver_payroll dp WHERE dp.employee_id = e.employee_id)
      AND NOT EXISTS (SELECT 1 FROM charters c WHERE c.assigned_driver_id = e.employee_id)
      AND NOT EXISTS (SELECT 1 FROM employee_expenses ee WHERE ee.employee_id = e.employee_id)
''')

safe_count = cur.fetchone()[0]
print(f'Safe to delete: {safe_count} LEGACY records (no FK refs)')
print()

# Show what's safe
cur.execute('''
    SELECT e.employee_id, e.employee_number, e.full_name
    FROM employees e
    WHERE e.employee_number LIKE 'LEGACY-%'
      AND NOT EXISTS (SELECT 1 FROM driver_payroll dp WHERE dp.employee_id = e.employee_id)
      AND NOT EXISTS (SELECT 1 FROM charters c WHERE c.assigned_driver_id = e.employee_id)
      AND NOT EXISTS (SELECT 1 FROM employee_expenses ee WHERE ee.employee_id = e.employee_id)
    ORDER BY e.employee_id
    LIMIT 15
''')

print('Safe to delete (samples):')
for emp_id, emp_num, name in cur.fetchall():
    print(f'  ID={emp_id:3d} | {emp_num:20s} | {name}')

cur.close()
conn.close()
