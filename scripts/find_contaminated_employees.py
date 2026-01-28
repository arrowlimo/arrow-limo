import psycopg2

pg_conn = psycopg2.connect(host='localhost', dbname='almsdata', user='postgres', password='***REMOVED***')
pg_cur = pg_conn.cursor()

print('=== Scanning for contaminated employee records ===\n')

# Look for suspicious names that don't look like people
pg_cur.execute('''
    SELECT employee_id, full_name, employee_category, position
    FROM employees
    WHERE full_name IS NOT NULL
    ORDER BY employee_id
''')

suspicious = []
for emp_id, full_name, category, position in pg_cur.fetchall():
    name_lower = full_name.lower()
    
    # Check for company/junk names
    is_suspicious = (
        'consulting' in name_lower or
        'technical' in name_lower or
        'invoice' in name_lower or
        'purposes' in name_lower or
        'cal-red' in name_lower or
        full_name.startswith('D') and len(full_name.split()) == 1  # single letter + numbers
    )
    
    if is_suspicious:
        suspicious.append((emp_id, full_name, category, position))
        print(f'⚠️  ID {emp_id:4} | {full_name:40} | {category} | {position}')

print(f'\nFound {len(suspicious)} suspicious employee records')

pg_cur.close()
pg_conn.close()
