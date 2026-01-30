import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()

print('2012 T4 RECORDS WITH MISSING DATA:\n')

# Check rows with NULL employee_id
cur.execute('''
    SELECT 
        employee_id, 
        box_14_employment_income,
        box_22_income_tax,
        created_at
    FROM employee_t4_records
    WHERE tax_year = 2012
    AND employee_id IS NULL
''')
null_rows = cur.fetchall()
print(f'Orphaned rows (employee_id = NULL): {len(null_rows)}')
for emp_id, box_14, box_22, created_at in null_rows:
    print(f'  emp_id=NULL, income={box_14}, tax={box_22}, created={created_at}')

# Check rows with employees missing SIN
cur.execute('''
    SELECT 
        etr.employee_id,
        e.full_name,
        e.t4_sin,
        etr.box_14_employment_income,
        etr.box_22_income_tax
    FROM employee_t4_records etr
    LEFT JOIN employees e ON etr.employee_id = e.employee_id
    WHERE etr.tax_year = 2012
    AND etr.employee_id IS NOT NULL
    AND (e.t4_sin IS NULL OR e.t4_sin = '')
    ORDER BY etr.employee_id
''')
rows = cur.fetchall()
print(f'\nRows with employees missing SIN: {len(rows)}')
for emp_id, name, sin, box_14, box_22 in rows:
    s = sin if sin else '(NULL)'
    print(f'  emp_id={emp_id}: {name}, SIN={s}, income={box_14}')

print('\n\nSUMMARY:')
print('The 2012 T4 records may have been imported incorrectly or from legacy data.')
print('Options:')
print('1. Delete orphaned rows (employee_id = NULL)')
print('2. Populate missing SINs for the 4 employees by cross-referencing')
print('3. Audit the source of 2012 T4 import to prevent future corruption')

cur.close()
conn.close()
