import pyodbc
from pprint import pprint
reserves = ['012144','012237','007504']
conn = pyodbc.connect(r"Driver={Microsoft Access Driver (*.mdb, *.accdb)};DBQ=L:\limo\db\lms2026d.mdb;")
cur = conn.cursor()
for table in ['Reserve','Charge','Payment']:
    print(f'===== {table} =====')
    rows = cur.execute(f"SELECT * FROM [{table}] WHERE Reserve_No IN ({','.join('?' for _ in reserves)})", reserves).fetchall()
    cols = [d[0] for d in cur.description]
    print('cols:', cols)
    for r in rows:
        print(dict(zip(cols, r)))
    print()
conn.close()
