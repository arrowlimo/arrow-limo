import pyodbc
import psycopg2

# Connect to LMS
lms_conn_str = r'Driver={Microsoft Access Driver (*.mdb, *.accdb)};DBQ=L:\limo\backups\lms.mdb;'
lms_conn = pyodbc.connect(lms_conn_str)
lms_cur = lms_conn.cursor()

# Connect to PostgreSQL
pg_conn = psycopg2.connect(host='localhost', dbname='almsdata', user='postgres', password='***REDACTED***')
pg_cur = pg_conn.cursor()

print('=== LMS Reserve data coverage ===\n')

# Get date range in LMS
lms_cur.execute('SELECT MIN(PU_Date), MAX(PU_Date) FROM Reserve WHERE PU_Date IS NOT NULL')
lms_min, lms_max = lms_cur.fetchone()
print(f'LMS Reserve data: {lms_min} to {lms_max}')

# Count total reserves in LMS
lms_cur.execute('SELECT Reserve_No FROM Reserve WHERE Reserve_No IS NOT NULL')
lms_reserves = set(row[0].strip() if row[0] else None for row in lms_cur.fetchall())
lms_reserves.discard(None)
print(f'Total unique reserves in LMS: {len(lms_reserves)}')

# Check PostgreSQL charters
pg_cur.execute('SELECT COUNT(*) FROM charters')
pg_count = pg_cur.fetchone()[0]
print(f'Total charters in PostgreSQL: {pg_count}')

# Check overlap
pg_cur.execute('SELECT COUNT(*) FROM charters WHERE employee_id IS NULL')
null_count = pg_cur.fetchone()[0]
print(f'Charters with NULL employee_id: {null_count}')
print(f'Charters with employee_id set: {pg_count - null_count}')

lms_cur.close()
lms_conn.close()
pg_cur.close()
pg_conn.close()
