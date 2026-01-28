import pyodbc
import psycopg2

# Connect to LMS
lms_conn_str = r'Driver={Microsoft Access Driver (*.mdb, *.accdb)};DBQ=L:\limo\backups\lms.mdb;'
lms_conn = pyodbc.connect(lms_conn_str)
lms_cur = lms_conn.cursor()

# Connect to PostgreSQL
pg_conn = psycopg2.connect(host='localhost', dbname='almsdata', user='postgres', password='***REMOVED***')
pg_cur = pg_conn.cursor()

print('=== Building LMS -> ALMS mapping by NAME ===\n')

# Get LMS drivers with their codes and names
lms_cur.execute('SELECT DISTINCT Driver, Name FROM Drivers WHERE Driver IS NOT NULL ORDER BY Driver')
lms_drivers = lms_cur.fetchall()
print(f'Found {len(lms_drivers)} LMS drivers\n')

# Build ALMS name lookup
pg_cur.execute('SELECT employee_id, full_name FROM employees ORDER BY employee_id')
alms_map = {}
for emp_id, name in pg_cur.fetchall():
    if name:
        alms_map[name.strip()] = emp_id

# Match by name
matches = []
mismatches = []

for lms_code, lms_name in lms_drivers:
    lms_code = lms_code.strip() if lms_code else None
    lms_name = lms_name.strip() if lms_name else None
    
    if lms_name in alms_map:
        emp_id = alms_map[lms_name]
        matches.append((lms_code, lms_name, emp_id))
        print(f'✅ {lms_code:6} {lms_name:35} → Employee ID {emp_id}')
    else:
        mismatches.append((lms_code, lms_name))
        print(f'❌ {lms_code:6} {lms_name:35} → NOT FOUND')

print(f'\n✅ Matched: {len(matches)}')
print(f'❌ Not found: {len(mismatches)}')

if mismatches:
    print(f'\nMismatches to investigate:')
    for code, name in mismatches[:10]:
        print(f'  {code} = {name}')

lms_cur.close()
lms_conn.close()
pg_cur.close()
pg_conn.close()
