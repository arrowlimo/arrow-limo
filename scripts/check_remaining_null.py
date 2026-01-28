import psycopg2

pg_conn = psycopg2.connect(host='localhost', dbname='almsdata', user='postgres', password='***REMOVED***')
pg_cur = pg_conn.cursor()

print('=== Remaining charters with NULL employee_id ===\n')

pg_cur.execute('''
    SELECT status, COUNT(*) as cnt
    FROM charters
    WHERE employee_id IS NULL
    GROUP BY status
    ORDER BY cnt DESC
''')

for status, count in pg_cur.fetchall():
    print(f'  status="{status}": {count}')

pg_cur.close()
pg_conn.close()
