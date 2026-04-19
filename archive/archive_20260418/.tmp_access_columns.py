import pyodbc
conn = pyodbc.connect(r"Driver={Microsoft Access Driver (*.mdb, *.accdb)};DBQ=L:\limo\db\lms2026d.mdb;")
cur = conn.cursor()
for table in ['Reserve','Charge','Payment','Deposit','Invoices','WebRes']:
    print(f'--- {table} ---')
    cols = []
    for row in cur.columns(table=table):
        cols.append((row.column_name, row.type_name, row.column_size))
    for c in cols:
        print(f'{c[0]} | {c[1]} | {c[2]}')
    print()
conn.close()
