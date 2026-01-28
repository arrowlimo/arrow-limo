import psycopg2

pg_conn = psycopg2.connect(host='localhost', dbname='almsdata', user='postgres', password='***REMOVED***')
pg_cur = pg_conn.cursor()

contaminated_ids = [69, 112]

print('=== Deleting contaminated employee records ===\n')

try:
    for emp_id in contaminated_ids:
        pg_cur.execute('DELETE FROM employees WHERE employee_id = %s', (emp_id,))
        print(f'✅ Deleted employee ID {emp_id}')
    
    pg_conn.commit()
    print(f'\n✅ Committed: {len(contaminated_ids)} contaminated records deleted')
except Exception as e:
    pg_conn.rollback()
    print(f'❌ Error: {e}')
finally:
    pg_cur.close()
    pg_conn.close()
