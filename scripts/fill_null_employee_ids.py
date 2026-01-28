import pyodbc
import psycopg2

# Connect to LMS
lms_conn_str = r'Driver={Microsoft Access Driver (*.mdb, *.accdb)};DBQ=L:\limo\backups\lms.mdb;'
lms_conn = pyodbc.connect(lms_conn_str)
lms_cur = lms_conn.cursor()

# Connect to PostgreSQL
pg_conn = psycopg2.connect(host='localhost', dbname='almsdata', user='postgres', password='***REMOVED***')
pg_cur = pg_conn.cursor()

# Build mapping of LMS driver name -> ALMS employee_id
pg_cur.execute('SELECT employee_id, full_name FROM employees ORDER BY employee_id')
alms_map = {}
for emp_id, name in pg_cur.fetchall():
    if name:
        alms_map[name.strip()] = emp_id

print('=== Updating charters with missing employee_id ===\n')

# Get charters with NULL employee_id
pg_cur.execute('''
    SELECT reserve_number, charter_date
    FROM charters
    WHERE employee_id IS NULL
    ORDER BY charter_date DESC
    LIMIT 100
''')
null_charters = pg_cur.fetchall()
print(f'Found {len(null_charters)} charters with NULL employee_id\n')

updated = 0
not_found = 0
mismatches = []

# For each charter, find the driver in LMS and map to employee
for reserve_number, charter_date in null_charters:
    # Find in LMS
    lms_cur.execute('''
        SELECT Driver, Name FROM Drivers 
        WHERE EXISTS (
            SELECT 1 FROM Reserve 
            WHERE Reserve_No = ? AND Driver = Drivers.Driver
        )
    ''', (reserve_number,))
    lms_row = lms_cur.fetchone()
    
    if lms_row:
        lms_code, lms_name = lms_row
        lms_code = lms_code.strip() if lms_code else None
        lms_name = lms_name.strip() if lms_name else None
        
        if lms_name in alms_map:
            emp_id = alms_map[lms_name]
            pg_cur.execute('''
                UPDATE charters
                SET employee_id = %s
                WHERE reserve_number = %s
            ''', (emp_id, reserve_number))
            print(f'✅ {reserve_number} | {lms_code:6} {lms_name:30} → emp_id {emp_id}')
            updated += 1
        else:
            mismatches.append((reserve_number, lms_code, lms_name))
            print(f'❌ {reserve_number} | {lms_code:6} {lms_name:30} → NOT FOUND')
            not_found += 1
    else:
        print(f'⚠️  {reserve_number} | Driver not found in LMS')

pg_conn.commit()
print(f'\n✅ Updated: {updated}')
print(f'❌ Not found: {not_found}')
print(f'\n✅ Committed {updated} charters with employee_id')

lms_cur.close()
lms_conn.close()
pg_cur.close()
pg_conn.close()
