#!/usr/bin/env python3
"""
Show LMS driver records that were not matched to any employee in the database.
"""
import os
import psycopg2
import psycopg2.extras as extras

try:
    import pyodbc
except Exception:
    print("pyodbc required")
    raise

PG = dict(
    host=os.environ.get("DB_HOST", "localhost"),
    dbname=os.environ.get("DB_NAME", "almsdata"),
    user=os.environ.get("DB_USER", "postgres"),
    password=os.environ.get("DB_PASSWORD", "***REMOVED***"),
    port=int(os.environ.get("DB_PORT", "5432")),
)

ROOT = os.path.dirname(os.path.dirname(__file__))
MDB_PATH = os.path.join(ROOT, 'backups', 'lms.mdb')

def connect_access(path):
    conn = pyodbc.connect(rf"Driver={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={path};")
    return conn

def norm(s):
    return (s or "").strip().lower()

def main():
    # Fetch all LMS drivers
    ac = connect_access(MDB_PATH)
    cur = ac.cursor()
    cur.execute("SELECT * FROM Drivers")
    raw_cols = [d[0] for d in cur.description]
    lms_drivers = []
    for r in cur.fetchall():
        rec = {raw_cols[i]: r[i] for i in range(len(r))}
        lms_drivers.append(rec)
    
    # Fetch all employees
    with psycopg2.connect(**PG) as conn:
        with conn.cursor(cursor_factory=extras.DictCursor) as cur:
            cur.execute("SELECT employee_id, employee_number, full_name FROM employees")
            employees = cur.fetchall()
    
    emp_by_num = {str(e['employee_number']).strip().upper(): e for e in employees if e.get('employee_number')}
    emp_by_name = {norm(e['full_name']): e for e in employees if e.get('full_name')}
    
    not_matched = []
    for lms in lms_drivers:
        code = str(lms.get('Driver') or lms.get('driver') or lms.get('code') or lms.get('Code') or lms.get('number') or '').strip().upper()
        name = str(lms.get('Name') or lms.get('name') or '').strip()
        matched = False
        if code and code in emp_by_num:
            matched = True
        elif norm(name) in emp_by_name:
            matched = True
        if not matched:
            not_matched.append({
                'lms_code': code or '(blank)',
                'lms_name': name or '(blank)',
            })
    
    print(f"LMS Driver Records: {len(lms_drivers)}")
    print(f"Matched/Updated: {len(lms_drivers) - len(not_matched)}")
    print(f"Not Matched: {len(not_matched)}\n")
    
    if not_matched:
        print("NOT MATCHED (no employee_number or full_name match):")
        for i, rec in enumerate(not_matched, 1):
            print(f"  {i}. Code: {rec['lms_code']}, Name: {rec['lms_name']}")
    else:
        print("All LMS drivers matched to employees.")

if __name__ == '__main__':
    main()
