#!/usr/bin/env python3
import pyodbc

LMS_PATH = r"L:\limo\lms.mdb"

def get_conn():
    conn_str = f'DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={LMS_PATH};'
    return pyodbc.connect(conn_str)

TABLES = ["Payment", "Deposit", "Reserve"]

with get_conn() as conn:
    cur = conn.cursor()
    for t in TABLES:
        print(f"\n=== {t} columns ===")
        try:
            cols = list(cur.columns(table=t))
            for c in cols:
                print(f"  {c.column_name} ({c.type_name})")
        except Exception as e:
            print(f"  Could not list columns: {e}")
        print(f"\nSample rows from {t}:")
        try:
            cur.execute(f"SELECT TOP 3 * FROM [{t}]")
            rows = cur.fetchall()
            names = [d[0] for d in cur.description]
            for i, r in enumerate(rows):
                print(f"  Row {i+1}:")
                for j, v in enumerate(r):
                    print(f"    {names[j]}: {v}")
        except Exception as e:
            print(f"  Could not fetch sample rows: {e}")
