#!/usr/bin/env python3
"""
Extract and preview schema/tables from LMS Access DB via ODBC.
Outputs: reports/lms_access_schema_preview.csv
"""
import os
import csv
import pyodbc

ACCESS_PATH = r'L:\limo\docs\lms.mdb'
CSV_OUT = r'l:/limo/reports/lms_access_schema_preview.csv'

conn_str = (
    r'DRIVER={Microsoft Access Driver (*.mdb, *.accdb)};'
    f'DBQ={ACCESS_PATH};'
)

def main():
    os.makedirs(os.path.dirname(CSV_OUT), exist_ok=True)
    with pyodbc.connect(conn_str, autocommit=True) as conn:
        cursor = conn.cursor()
        tables = [row.table_name for row in cursor.tables(tableType='TABLE')]
        with open(CSV_OUT, 'w', newline='', encoding='utf-8') as f:
            w = csv.writer(f)
            w.writerow(['table_name','column_name','type_name','nullable'])
            for t in tables:
                for col in cursor.columns(table=t):
                    w.writerow([t, col.column_name, col.type_name, col.nullable])
    print('Schema preview written to', CSV_OUT)

if __name__ == '__main__':
    main()
