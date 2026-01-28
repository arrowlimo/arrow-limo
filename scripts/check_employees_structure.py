import psycopg2

pg_conn = psycopg2.connect(host='localhost', dbname='almsdata', user='postgres', password='***REMOVED***')
pg_cur = pg_conn.cursor()

print('=== Employees table structure ===')
pg_cur.execute('''
    SELECT column_name, data_type
    FROM information_schema.columns
    WHERE table_name = 'employees'
    ORDER BY ordinal_position
''')
cols = pg_cur.fetchall()
for col in cols:
    print(f'  {col[0]:30} {col[1]}')

print('\n=== Sample employees ===')
pg_cur.execute('SELECT employee_id, full_name FROM employees LIMIT 5')
rows = pg_cur.fetchall()
for row in rows:
    print(f'  {row[0]:3} {row[1]}')

pg_cur.close()
pg_conn.close()
