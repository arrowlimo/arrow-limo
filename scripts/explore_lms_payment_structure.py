import pyodbc

# Connect to LMS
lms_conn_str = r'Driver={Microsoft Access Driver (*.mdb, *.accdb)};DBQ=L:\limo\backups\lms.mdb;'
lms_conn = pyodbc.connect(lms_conn_str)
lms_cur = lms_conn.cursor()

print('=== LMS PAYMENT TABLE STRUCTURE ===\n')

# List all tables that might contain payment data
lms_cur.execute("SELECT * FROM [Payment] WHERE 1=0")
cols = [desc[0] for desc in lms_cur.description]
print('Payment table columns:')
for i, col in enumerate(cols):
    print(f'  {i+1}. {col}')

print('\n\n=== SAMPLE PAYMENT RECORDS ===\n')
lms_cur.execute('SELECT * FROM [Payment] LIMIT 3')
rows = lms_cur.fetchall()
if rows:
    for row in rows:
        print(f'Record: {dict(zip(cols, row))}')
        print()

# Check Reserve table structure
print('\n=== LMS RESERVE TABLE STRUCTURE ===\n')
lms_cur.execute("SELECT * FROM Reserve WHERE 1=0")
reserve_cols = [desc[0] for desc in lms_cur.description]
print('Reserve table columns (first 20):')
for col in reserve_cols[:20]:
    print(f'  {col}')
if len(reserve_cols) > 20:
    print(f'  ... and {len(reserve_cols) - 20} more')

lms_cur.close()
lms_conn.close()
