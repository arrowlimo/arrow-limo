#!/usr/bin/env python3
"""
Inspect the LMS Drivers table structure and show sample data.
"""
import os
try:
    import pyodbc
except Exception:
    print("pyodbc required")
    raise

ROOT = os.path.dirname(os.path.dirname(__file__))
MDB_PATH = os.path.join(ROOT, 'backups', 'lms.mdb')

def connect_access(path):
    conn = pyodbc.connect(rf"Driver={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={path};")
    return conn

def main():
    ac = connect_access(MDB_PATH)
    cur = ac.cursor()
    
    # Get column names
    cur.execute("SELECT * FROM Drivers WHERE 1=0")
    columns = [d[0] for d in cur.description]
    
    print("LMS Drivers Table Columns:")
    for i, col in enumerate(columns, 1):
        print(f"  {i}. {col}")
    
    # Show first 5 records
    cur.execute("SELECT * FROM Drivers")
    rows = cur.fetchmany(5)
    
    print(f"\n\nFirst 5 Records (showing key columns):")
    for i, row in enumerate(rows, 1):
        rec = {columns[j]: row[j] for j in range(len(columns))}
        print(f"\nRecord {i}:")
        for col in columns:
            if rec[col] is not None and str(rec[col]).strip():
                print(f"  {col}: {rec[col]}")
    
    # Check for Paula Kettle specifically
    print("\n\nSearching for 'Kettle Paula' or 'Paula Kettle':")
    cur.execute("SELECT * FROM Drivers WHERE name LIKE '%Kettle%' OR name LIKE '%Paula%'")
    for row in cur.fetchall():
        rec = {columns[j]: row[j] for j in range(len(columns))}
        print("\nFound:")
        for col in columns:
            if rec[col] is not None and str(rec[col]).strip():
                print(f"  {col}: {rec[col]}")

if __name__ == '__main__':
    main()
