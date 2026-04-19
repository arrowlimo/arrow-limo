import pyodbc
conn = pyodbc.connect(r"Driver={Microsoft Access Driver (*.mdb, *.accdb)};DBQ=L:\limo\db\lms2026d.mdb;")
cur = conn.cursor()
tables = []
for row in cur.tables(tableType='TABLE'):
    name = row.table_name
    if any(k in name.lower() for k in ['res','pay','charge','invoice','deposit','receipt','tran','folio','bill']):
        tables.append(name)
print('\n'.join(sorted(set(tables))))
conn.close()
