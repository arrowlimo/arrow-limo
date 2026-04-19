import pyodbc
conn = pyodbc.connect(r"DRIVER={Microsoft Access Driver (*.mdb, *.accdb)};DBQ=L:\limo\db\lms2026d.mdb;")
cur = conn.cursor()
print('TABLES')
for row in cur.tables(tableType='TABLE'):
    if row.table_name.lower() == 'payment':
        print('FOUND', row.table_name)
print('COLUMNS')
for row in cur.columns(table='Payment'):
    print(row.column_name, row.type_name)
conn.close()
