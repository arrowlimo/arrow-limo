import psycopg2

pg_conn = psycopg2.connect(host='localhost', dbname='almsdata', user='postgres', password='***REMOVED***')
pg_cur = pg_conn.cursor()

contaminated_ids = [69, 112]

print('=== Checking references to contaminated employees ===\n')

for emp_id in contaminated_ids:
    pg_cur.execute('SELECT COUNT(*) FROM charters WHERE employee_id = %s', (emp_id,))
    count = pg_cur.fetchone()[0]
    print(f'Employee ID {emp_id}: {count} charters reference this ID')
    
    if count > 0:
        pg_cur.execute('SELECT reserve_number, charter_date FROM charters WHERE employee_id = %s LIMIT 5', (emp_id,))
        for row in pg_cur.fetchall():
            print(f'  - {row[0]} on {row[1]}')

pg_cur.close()
pg_conn.close()
