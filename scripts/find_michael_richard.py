import psycopg2

pg_conn = psycopg2.connect(host='localhost', dbname='almsdata', user='postgres', password='***REMOVED***')
pg_cur = pg_conn.cursor()

print('=== Looking for Richard, Michael P. in PostgreSQL ===')
pg_cur.execute('SELECT employee_id, full_name FROM employees WHERE full_name ILIKE %s', ('%Richard%',))
rows = pg_cur.fetchall()
if rows:
    for row in rows:
        print(f'ID: {row[0]}, Name: {row[1]}')
else:
    print('Not found with Richard. Try Michael:')
    pg_cur.execute('SELECT employee_id, full_name FROM employees WHERE full_name ILIKE %s ORDER BY employee_id', ('%Michael%',))
    rows = pg_cur.fetchall()
    for row in rows:
        print(f'ID: {row[0]}, Name: {row[1]}')

pg_cur.close()
pg_conn.close()
