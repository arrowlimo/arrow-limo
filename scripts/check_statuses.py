import pyodbc
import psycopg2

# Connect to LMS
lms_conn_str = r'Driver={Microsoft Access Driver (*.mdb, *.accdb)};DBQ=L:\limo\backups\lms.mdb;'
lms_conn = pyodbc.connect(lms_conn_str)
lms_cur = lms_conn.cursor()

# Connect to PostgreSQL
pg_conn = psycopg2.connect(host='localhost', dbname='almsdata', user='postgres', password='***REMOVED***')
pg_cur = pg_conn.cursor()

print('=== STATUS VALUES ===\n')

# Check LMS statuses
print('LMS Reserve statuses:')
lms_cur.execute('SELECT DISTINCT Status FROM Reserve WHERE Status IS NOT NULL ORDER BY Status')
for row in lms_cur.fetchall():
    status = row[0].strip() if row[0] else None
    lms_cur.execute('SELECT COUNT(*) FROM Reserve WHERE Status = ?', (status,))
    count = lms_cur.fetchone()[0]
    print(f'  "{status}": {count}')

# Check PostgreSQL statuses
print('\nALMS charters statuses:')
pg_cur.execute('''
    SELECT DISTINCT status, COUNT(*) as cnt
    FROM charters
    GROUP BY status
    ORDER BY cnt DESC
''')
for status, count in pg_cur.fetchall():
    print(f'  "{status}": {count}')

print('\nALMS columns in charters table:')
pg_cur.execute('''
    SELECT column_name, data_type
    FROM information_schema.columns
    WHERE table_name = 'charters'
    AND column_name LIKE '%status%'
    ORDER BY ordinal_position
''')
for col, dtype in pg_cur.fetchall():
    print(f'  {col}: {dtype}')

lms_cur.close()
lms_conn.close()
pg_cur.close()
pg_conn.close()
