import psycopg2

pg_conn = psycopg2.connect(host='localhost', dbname='almsdata', user='postgres', password='***REDACTED***')
pg_cur = pg_conn.cursor()

print('=== Cleaning up all contaminated references ===\n')

try:
    # Clear assigned_driver_id references
    for emp_id in [69, 112]:
        pg_cur.execute('''
            SELECT COUNT(*) FROM charters 
            WHERE assigned_driver_id = %s
        ''', (emp_id,))
        count = pg_cur.fetchone()[0]
        if count > 0:
            pg_cur.execute('''
                UPDATE charters 
                SET assigned_driver_id = NULL 
                WHERE assigned_driver_id = %s
            ''', (emp_id,))
            print(f'✅ Updated {count} charters (assigned_driver_id)')
    
    # Clear driver_employee_mapping references
    for emp_id in [69, 112]:
        pg_cur.execute('''
            SELECT COUNT(*) FROM driver_employee_mapping 
            WHERE employee_id = %s
        ''', (emp_id,))
        count = pg_cur.fetchone()[0]
        if count > 0:
            pg_cur.execute('''
                DELETE FROM driver_employee_mapping 
                WHERE employee_id = %s
            ''', (emp_id,))
            print(f'✅ Deleted {count} rows from driver_employee_mapping (employee_id={emp_id})')
    
    # Now delete the contaminated employees
    for emp_id in [69, 112]:
        pg_cur.execute('DELETE FROM employees WHERE employee_id = %s', (emp_id,))
        print(f'✅ Deleted contaminated employee ID {emp_id}')
    
    pg_conn.commit()
    print(f'\n✅ Committed: All contaminated employee records cleaned up')
except Exception as e:
    pg_conn.rollback()
    print(f'❌ Error: {e}')
finally:
    pg_cur.close()
    pg_conn.close()
