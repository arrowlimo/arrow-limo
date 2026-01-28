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

print('=== Bulk updating charters via LMS Reserve + Drivers ===\n')

# Get all LMS reserves with driver names
lms_cur.execute('''
    SELECT DISTINCT r.Reserve_No, d.Name
    FROM Reserve r
    LEFT JOIN Drivers d ON r.Driver = d.Driver
    WHERE r.Reserve_No IS NOT NULL
    ORDER BY r.Reserve_No
''')

all_reserves = lms_cur.fetchall()
print(f'Processing {len(all_reserves)} LMS reserves...\n')

updated = 0
not_found = 0
already_set = 0

for lms_reserve_num, lms_driver_name in all_reserves:
    if not lms_reserve_num:
        continue
    
    lms_reserve_num = str(lms_reserve_num).strip()
    lms_driver_name = lms_driver_name.strip() if lms_driver_name else None
    
    # Check if this charter exists in PostgreSQL
    pg_cur.execute('SELECT employee_id FROM charters WHERE reserve_number = %s LIMIT 1', (lms_reserve_num,))
    pg_row = pg_cur.fetchone()
    
    if not pg_row:
        continue  # Charter doesn't exist in PG
    
    emp_id_in_pg = pg_row[0]
    
    if emp_id_in_pg is not None:
        already_set += 1
        continue  # Already has an employee_id
    
    # Try to match driver name
    if lms_driver_name and lms_driver_name in alms_map:
        emp_id = alms_map[lms_driver_name]
        pg_cur.execute('UPDATE charters SET employee_id = %s WHERE reserve_number = %s', (emp_id, lms_reserve_num))
        updated += 1
        if updated <= 10:
            print(f'✅ {lms_reserve_num} ← {lms_driver_name} → emp_id {emp_id}')
    else:
        not_found += 1
        if not_found <= 5:
            print(f'❌ {lms_reserve_num} ← Driver "{lms_driver_name}" not found')

pg_conn.commit()
print(f'\n✅ Updated: {updated}')
print(f'✅ Already had employee_id: {already_set}')
print(f'❌ Driver not found: {not_found}')
print(f'\n✅ Committed {updated} charters')

lms_cur.close()
lms_conn.close()
pg_cur.close()
pg_conn.close()
