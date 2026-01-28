import pyodbc

# Connect to LMS
lms_conn_str = r'Driver={Microsoft Access Driver (*.mdb, *.accdb)};DBQ=L:\limo\backups\lms.mdb;'
lms_conn = pyodbc.connect(lms_conn_str)
lms_cur = lms_conn.cursor()

print('=== Reserve records with blank Driver field ===\n')

lms_cur.execute('SELECT COUNT(*) FROM Reserve WHERE Driver IS NULL')
blank_count = lms_cur.fetchone()[0]

lms_cur.execute('SELECT Reserve_No FROM Reserve WHERE Reserve_No IS NOT NULL')
total_count = len(lms_cur.fetchall())

print(f'Reserves with blank driver: {blank_count}')
print(f'Total reserves: {total_count}')
print(f'Percentage: {100*blank_count/total_count:.1f}%')

lms_cur.close()
lms_conn.close()
