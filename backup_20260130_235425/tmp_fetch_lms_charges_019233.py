import pyodbc, json
conn = pyodbc.connect(r"Driver={Microsoft Access Driver (*.mdb, *.accdb)};DBQ=L:\\limo\\backups\\lms.mdb;")
cur = conn.cursor()
cur.execute("SELECT ChargeID, Reserve_No, Amount, Desc FROM Charge WHERE Reserve_No = ? ORDER BY ChargeID", ('019233',))
rows = []
for r in cur.fetchall():
    rows.append({
        'charge_id': r[0],
        'reserve': r[1],
        'amount': float(r[2] or 0),
        'desc': (str(r[3]).strip() if r[3] is not None else '')
    })
print(json.dumps(rows, indent=2))
