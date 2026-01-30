import pyodbc
import psycopg2
import re

# Connect to LMS
lms_conn_str = r'Driver={Microsoft Access Driver (*.mdb, *.accdb)};DBQ=L:\limo\backups\lms.mdb;'
lms_conn = pyodbc.connect(lms_conn_str)
lms_cur = lms_conn.cursor()

# Connect to PostgreSQL
pg_conn = psycopg2.connect(host='localhost', dbname='almsdata', user='postgres', password='***REDACTED***')
pg_cur = pg_conn.cursor()

# Build mapping of LMS driver code -> ALMS employee_id using driver_code field
def normalize_lms_code(code):
    """Convert LMS code (Dr09, D29) to ALMS format (DR009, D029)"""
    if not code:
        return None
    code = code.strip().upper()
    # Extract letters and numbers
    match = re.match(r'^([A-Z]+)(\d+)$', code)
    if match:
        letters = match.group(1)
        numbers = match.group(2)
        # Pad numbers to 3 digits
        return f"{letters}{numbers.zfill(3)}"
    return code

# Get ALMS driver codes
pg_cur.execute('''
    SELECT employee_id, driver_code
    FROM employees
    WHERE driver_code IS NOT NULL
    ORDER BY employee_id
''')
alms_map = {}
for emp_id, code in pg_cur.fetchall():
    if code:
        alms_map[code.strip().upper()] = emp_id

print('=== Creating LMS -> ALMS mapping ===\n')

# Get unique LMS drivers from Reserve table
lms_cur.execute('SELECT DISTINCT Driver FROM Reserve WHERE Driver IS NOT NULL ORDER BY Driver')
lms_drivers = [row[0].strip() if row[0] else None for row in lms_cur.fetchall()]
lms_drivers = [d for d in lms_drivers if d]  # Filter None

print(f'LMS Drivers: {len(lms_drivers)} unique codes')
print(f'ALMS Driver Codes: {len(alms_map)} stored in employees\n')

# Try to match
matches = 0
mismatches = []

for lms_code in lms_drivers:
    normalized = normalize_lms_code(lms_code)
    if normalized in alms_map:
        emp_id = alms_map[normalized]
        matches += 1
        print(f'✅ {lms_code:6} → {normalized:8} → Employee ID {emp_id}')
    else:
        mismatches.append(lms_code)
        print(f'❌ {lms_code:6} → {normalized:8} → NOT FOUND')

print(f'\nMatches: {matches}/{len(lms_drivers)}')
if mismatches:
    print(f'Mismatches: {mismatches}')

lms_cur.close()
lms_conn.close()
pg_cur.close()
pg_conn.close()
