import psycopg2

conn = psycopg2.connect('host=localhost dbname=almsdata user=postgres password=***REDACTED***')
cur = conn.cursor()

# Get employees that look like real people (not addresses, not CPP deductions, etc.)
cur.execute("""
SELECT employee_id, full_name, employee_category, position, is_chauffeur, quickbooks_id
FROM employees
WHERE full_name NOT ILIKE '%@%'
  AND full_name NOT ILIKE 'PO Box%'
  AND full_name NOT ILIKE '%CPP%'
  AND full_name NOT ILIKE '%EI -%'
  AND full_name NOT ILIKE '%Canada%'
  AND full_name NOT ILIKE 'AB%'
  AND full_name NOT ILIKE '%Red Deer%'
  AND full_name NOT ILIKE '%Street%'
  AND full_name NOT ILIKE '%Avenue%'
  AND full_name !~ '^[0-9]'
  AND LENGTH(full_name) < 50
ORDER BY full_name
""")

results = cur.fetchall()
print(f'\nReal-looking employees: {len(results)}\n')
print('='*100)

for emp_id, name, category, position, is_chauffeur, qb_id in results[:150]:
    driver_flag = '🚗' if is_chauffeur else '  '
    cat = (category or '')[:15]
    pos = (position or '')[:20]
    qb = f'QB:{qb_id}' if qb_id else ''
    print(f'  {emp_id:3d} {driver_flag} | {name:40s} | {cat:15s} | {pos:20s} | {qb}')

if len(results) > 150:
    print(f'\n... and {len(results)-150} more')
