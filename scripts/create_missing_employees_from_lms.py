#!/usr/bin/env python3
"""
Create DR114 (Ofougwuka Melissa) and DR128 (Manz, Robert) from LMS data.
"""
import os
import sys
import pyodbc
import psycopg2
import psycopg2.extras

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")
MDB_PATH = r"L:\limo\backups\lms.mdb"

# Connect to Access
ac_conn = pyodbc.connect(f"Driver={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={MDB_PATH};")
ac_cur = ac_conn.cursor()

# Fetch DR114 and DR128
ac_cur.execute("SELECT * FROM Drivers WHERE Driver IN ('DR114', 'DR128')")
cols = [d[0] for d in ac_cur.description]
rows = ac_cur.fetchall()

drivers = []
for row in rows:
    rec = {cols[i]: row[i] for i in range(len(cols))}
    drivers.append({
        'code': rec.get('Driver', '').strip(),
        'name': rec.get('Driver_Name', '').strip(),
        'license': rec.get('Lic1_no', '').strip() if rec.get('Lic1_no') else None,
        'license_exp': rec.get('Lic1_Exp'),
        'permit': rec.get('Lic2_no', '').strip() if rec.get('Lic2_no') else None,
        'permit_exp': rec.get('Lic2_Exp'),
        'sin': rec.get('Social_Sec', '').strip() if rec.get('Social_Sec') else None,
        'email': rec.get('E_Mail', '').strip() if rec.get('E_Mail') else None,
        'phone': rec.get('Home_Ph', '').strip() if rec.get('Home_Ph') else None,
        'cell': rec.get('Work_Ph', '').strip() if rec.get('Work_Ph') else None,
        'hire_date': rec.get('Hire_Date'),
        'address': rec.get('Address', '').strip() if rec.get('Address') else None,
        'city': rec.get('City', '').strip() if rec.get('City') else None,
        'province': rec.get('Prov', '').strip() if rec.get('Prov') else None,
        'postal': rec.get('Postal_Code', '').strip() if rec.get('Postal_Code') else None,
    })

ac_cur.close()
ac_conn.close()

print(f"Found {len(drivers)} employees to create:")
for d in drivers:
    print(f"  {d['code']} - {d['name']}")
    print(f"    License: {d['license']} (exp: {d['license_exp']})")
    print(f"    Permit: {d['permit']} (exp: {d['permit_exp']})")
    print(f"    SIN: {d['sin']}")
    print(f"    Email: {d['email']}")
    print(f"    Phone: {d['phone']} / Cell: {d['cell']}")
    print(f"    Address: {d['address']}, {d['city']}, {d['province']} {d['postal']}")

# Connect to PostgreSQL and insert
conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

try:
    for d in drivers:
        cur.execute("""
            INSERT INTO employees (
                employee_number, full_name, employment_status, is_chauffeur,
                driver_license_number, driver_license_expiry,
                chauffeur_permit_number, chauffeur_permit_expiry,
                t4_sin, email, phone, cell_phone, hire_date,
                street_address, city, province, postal_code
            ) VALUES (
                %s, %s, 'inactive', TRUE,
                %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s
            )
            RETURNING employee_id
        """, (
            d['code'], d['name'],
            d['license'], d['license_exp'], d['permit'], d['permit_exp'],
            d['sin'], d['email'], d['phone'], d['cell'], d['hire_date'],
            d['address'], d['city'], d['province'], d['postal']
        ))
        emp_id = cur.fetchone()[0]
        print(f"✅ Created employee_id={emp_id}: {d['code']} - {d['name']}")
    
    conn.commit()
    print(f"\n✅ Committed {len(drivers)} new employees")
    
except Exception as e:
    conn.rollback()
    print(f"❌ Rolled back: {e}")
    sys.exit(1)
finally:
    cur.close()
    conn.close()
