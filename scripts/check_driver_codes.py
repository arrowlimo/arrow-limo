import psycopg2

pg_conn = psycopg2.connect(host='localhost', dbname='almsdata', user='postgres', password='***REMOVED***')
pg_cur = pg_conn.cursor()

print('=== Employees with driver codes ===')
pg_cur.execute('''
    SELECT employee_id, full_name, driver_code
    FROM employees
    WHERE driver_code IS NOT NULL
    ORDER BY driver_code
''')
rows = pg_cur.fetchall()
for row in rows:
    print(f'  ID {row[0]:3} | {row[1]:30} | Code: {row[2]}')

print(f'\nTotal employees with driver codes: {len(rows)}')

pg_cur.close()
pg_conn.close()
