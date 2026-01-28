import pyodbc

lms_conn_str = r'Driver={Microsoft Access Driver (*.mdb, *.accdb)};DBQ=L:\limo\backups\lms.mdb;'
lms_conn = pyodbc.connect(lms_conn_str)
lms_cur = lms_conn.cursor()

print('=== Looking for Dr09 driver ===')
lms_cur.execute('SELECT Driver, Name FROM Drivers WHERE Driver = ?', ('Dr09',))
rows = lms_cur.fetchall()
if rows:
    for row in rows:
        print(f'{row[0]} = {row[1]}')
else:
    print('Dr09 not found. All driver codes:')
    lms_cur.execute('SELECT Driver, Name FROM Drivers ORDER BY Driver')
    rows = lms_cur.fetchall()
    for row in rows:
        code = str(row[0]).strip() if row[0] else ''
        print(f'{code:10} = {row[1]}')

lms_cur.close()
lms_conn.close()
