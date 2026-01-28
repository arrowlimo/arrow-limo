import pyodbc
import psycopg2

# Connect to LMS
lms_conn_str = r'Driver={Microsoft Access Driver (*.mdb, *.accdb)};DBQ=L:\limo\backups\lms.mdb;'
lms_conn = pyodbc.connect(lms_conn_str)
lms_cur = lms_conn.cursor()

# Connect to PostgreSQL
pg_conn = psycopg2.connect(host='localhost', dbname='almsdata', user='postgres', password='***REMOVED***')
pg_cur = pg_conn.cursor()

print('=== Closed charters with NULL employee_id ===\n')

# Sample 10 of them
pg_cur.execute('''
    SELECT reserve_number, charter_date, status
    FROM charters
    WHERE employee_id IS NULL
    AND status = 'Closed'
    LIMIT 10
''')

for pg_reserve, pg_date, pg_status in pg_cur.fetchall():
    # Check if in LMS
    lms_cur.execute('SELECT Reserve_No, Driver FROM Reserve WHERE Reserve_No = ?', (pg_reserve,))
    lms_row = lms_cur.fetchone()
    
    if lms_row:
        print(f'✅ {pg_reserve} | {pg_date} | LMS Driver: {lms_row[1]}')
    else:
        print(f'❌ {pg_reserve} | {pg_date} | NOT in LMS')

lms_cur.close()
lms_conn.close()
pg_cur.close()
pg_conn.close()
