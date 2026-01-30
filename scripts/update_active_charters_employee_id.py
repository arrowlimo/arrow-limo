import pyodbc
import psycopg2

# Connect to LMS
lms_conn_str = r'Driver={Microsoft Access Driver (*.mdb, *.accdb)};DBQ=L:\limo\backups\lms.mdb;'
lms_conn = pyodbc.connect(lms_conn_str)
lms_cur = lms_conn.cursor()

# Connect to PostgreSQL
pg_conn = psycopg2.connect(host='localhost', dbname='almsdata', user='postgres', password='***REDACTED***')
pg_cur = pg_conn.cursor()

# Build mapping of LMS driver name -> ALMS employee_id
pg_cur.execute('SELECT employee_id, full_name FROM employees ORDER BY employee_id')
alms_map = {}
for emp_id, name in pg_cur.fetchall():
    if name:
        alms_map[name.strip()] = emp_id

print('=== Update employee_id for ACTIVE charters only ===\n')

# LMS statuses that are "active" (not quotes/cancelled)
active_statuses = ['Closed', 'Posted', 'Paid in Full', 'UNCLOSED', '1 In Route', 'Changed']

# ALMS statuses to update (anything that's "closed" or "Closed", "Paid", etc.)
# Skip: blank, None, "cancelled", "Cancelled", "CANCELLED", "Cancelled $$"
skip_patterns = ['', 'None', 'cancelled', 'Cancelled', 'CANCELLED', 'refund_pair', 'Deposit', 'Waiting']

# Get charters with NULL employee_id that are NOT cancelled/quotes
pg_cur.execute('''
    SELECT c.reserve_number, c.status
    FROM charters c
    WHERE c.employee_id IS NULL
    AND c.status NOT IN ('', 'None', 'cancelled', 'Cancelled', 'CANCELLED', 
                         'Cancelled $$', 'refund_pair', 'Deposit Recvd', 'Waiting Deposit')
    ORDER BY c.reserve_number
    LIMIT 500
''')

null_charters = pg_cur.fetchall()
print(f'Found {len(null_charters)} "active" charters with NULL employee_id\n')

updated = 0
not_found = 0
already_has = 0

for pg_reserve, pg_status in null_charters:
    # Find in LMS
    lms_cur.execute('''
        SELECT r.Driver, d.Name FROM Reserve r
        LEFT JOIN Drivers d ON r.Driver = d.Driver
        WHERE r.Reserve_No = ?
    ''', (pg_reserve,))
    lms_row = lms_cur.fetchone()
    
    if lms_row:
        lms_code, lms_name = lms_row
        lms_code = lms_code.strip() if lms_code else None
        lms_name = lms_name.strip() if lms_name else None
        
        if lms_name and lms_name in alms_map:
            emp_id = alms_map[lms_name]
            pg_cur.execute('''
                UPDATE charters
                SET employee_id = %s
                WHERE reserve_number = %s
            ''', (emp_id, pg_reserve))
            updated += 1
            if updated <= 10:
                print(f'✅ {pg_reserve} | status={pg_status:25} | {lms_code} → {lms_name:30} → emp_id {emp_id}')
        else:
            not_found += 1
    else:
        not_found += 1

pg_conn.commit()
print(f'\n✅ Updated: {updated}')
print(f'❌ Not found: {not_found}')
print(f'\n✅ Committed {updated} charters')

lms_cur.close()
lms_conn.close()
pg_cur.close()
pg_conn.close()
