import pyodbc
ac_conn = pyodbc.connect(r"Driver={Microsoft Access Driver (*.mdb, *.accdb)};DBQ=L:\limo\backups\lms.mdb;")
ac_cur = ac_conn.cursor()
# First get all columns
ac_cur.execute("SELECT * FROM Drivers WHERE Driver IN ('DR114', 'DR128', 'Dr114', 'Dr128')")
cols = [d[0] for d in ac_cur.description]
print(f"Columns: {cols}")
print("\nLMS Data:")
for r in ac_cur.fetchall():
    rec = {cols[i]: r[i] for i in range(len(cols))}
    print(f"Code: {rec.get('Driver')}")
    for k, v in rec.items():
        if v and str(v).strip():
            print(f"  {k}: {v}")
ac_cur.close()
ac_conn.close()
