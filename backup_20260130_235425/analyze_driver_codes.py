import pyodbc
import psycopg2

# Connect to LMS
lms_conn_str = r'Driver={Microsoft Access Driver (*.mdb, *.accdb)};DBQ=L:\limo\backups\lms.mdb;'
lms_conn = pyodbc.connect(lms_conn_str)
lms_cur = lms_conn.cursor()

# Connect to PostgreSQL
pg_conn = psycopg2.connect(host='localhost', dbname='almsdata', user='postgres', password='***REDACTED***')
pg_cur = pg_conn.cursor()

# Get all LMS drivers
print('=== LMS Drivers (from Reserve) ===')
lms_cur.execute('SELECT DISTINCT Driver FROM Reserve WHERE Driver IS NOT NULL ORDER BY Driver')
lms_drivers = [row[0].strip() if row[0] else None for row in lms_cur.fetchall()]
print(f'Found {len(lms_drivers)} unique driver codes in LMS')
for code in lms_drivers[:20]:
    print(f'  {code}')
if len(lms_drivers) > 20:
    print(f'  ... and {len(lms_drivers) - 20} more')

# Get all ALMS driver codes
print('\n=== ALMS Driver Codes ===')
pg_cur.execute('SELECT DISTINCT driver_code FROM employees WHERE driver_code IS NOT NULL ORDER BY driver_code')
alms_codes = [row[0].strip() if row[0] else None for row in pg_cur.fetchall()]
print(f'Found {len(alms_codes)} unique driver codes in ALMS')
for code in alms_codes[:20]:
    print(f'  {code}')
if len(alms_codes) > 20:
    print(f'  ... and {len(alms_codes) - 20} more')

# Show mapping example
print('\n=== Mapping Example ===')
print('LMS format: Dr09, Dr03, D29')
print('ALMS format: DR009, DR003, D29')
print('Need to normalize: LMS uppercase + zero-pad to 3 digits')

lms_cur.close()
lms_conn.close()
pg_cur.close()
pg_conn.close()
