import pyodbc

lms_conn_str = r'Driver={Microsoft Access Driver (*.mdb, *.accdb)};DBQ=L:\limo\backups\lms.mdb;'
lms_conn = pyodbc.connect(lms_conn_str)
lms_cur = lms_conn.cursor()

# Check Charge table structure
lms_cur.execute('SELECT * FROM Charge WHERE 1=0')
cols = [desc[0] for desc in lms_cur.description]
print('=== LMS Charge table columns ===\n')
for col in cols:
    print(f'  {col}')

# Get a sample to understand the key
print('\n=== Sample Charge records ===\n')
lms_cur.execute('SELECT TOP 3 * FROM Charge')
for row in lms_cur.fetchall():
    print(dict(zip(cols, row)))
    print()

lms_cur.close()
lms_conn.close()
