import pyodbc

lms_conn_str = r'Driver={Microsoft Access Driver (*.mdb, *.accdb)};DBQ=L:\limo\backups\lms.mdb;'
lms_conn = pyodbc.connect(lms_conn_str)
lms_cur = lms_conn.cursor()

print('=== All LMS tables with "Payment" in name ===\n')
for table_info in lms_cur.tables():
    table_name = table_info[2]
    if 'payment' in table_name.lower():
        print(f'  {table_name}')

lms_cur.close()
lms_conn.close()
