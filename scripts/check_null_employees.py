import psycopg2

pg_conn = psycopg2.connect(host='localhost', dbname='almsdata', user='postgres', password='***REMOVED***')
pg_cur = pg_conn.cursor()

print('=== Charters with NULL employee_id ===')
pg_cur.execute('''
    SELECT COUNT(*) 
    FROM charters 
    WHERE employee_id IS NULL
''')
count = pg_cur.fetchone()[0]
print(f'Total charters with NULL employee_id: {count}\n')

print('Sample charters with NULL employee_id:')
pg_cur.execute('''
    SELECT reserve_number, charter_date, driver_name
    FROM charters
    WHERE employee_id IS NULL
    ORDER BY charter_date DESC
    LIMIT 20
''')
rows = pg_cur.fetchall()
for row in rows:
    print(f'  {row[0]} | {row[1]} | driver_name={row[2]}')

pg_cur.close()
pg_conn.close()
