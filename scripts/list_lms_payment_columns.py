import pyodbc

def main():
    path = r"L:\\limo\\backups\\lms.mdb"
    conn = pyodbc.connect(rf'Driver={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={path};')
    cur = conn.cursor()
    print("Payment columns:")
    for c in cur.columns(table='Payment'):
        print(f"- {c.column_name} | {c.type_name}")
    cur.execute("SELECT TOP 1 * FROM Payment")
    row = cur.fetchone()
    print("Sample row:")
    if row:
        print([str(v) for v in row])
    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
