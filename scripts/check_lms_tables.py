#!/usr/bin/env python3
"""
Check what tables exist in LMS.
"""

import pyodbc

LMS_PATH = r"L:\limo\backups\lms.mdb"

lms_conn_str = f"Driver={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={LMS_PATH};"
lms_conn = pyodbc.connect(lms_conn_str)
lms_cur = lms_conn.cursor()

print("Tables in LMS:")
print()

try:
    # Get list of tables
    tables = lms_cur.getTypeInfo()
    
    # List all tables
    for table in lms_conn.cursor().execute("SELECT name FROM MSysObjects WHERE Type=1 AND Flags=0").fetchall():
        print(f"  {table[0]}")
except Exception as e:
    print(f"Method 1 failed: {e}")
    print()
    print("Trying method 2...")
    
    # Try alternate method
    try:
        lms_cur.execute("SELECT TOP 1 * FROM tblReservation")
        print("Found: tblReservation")
    except:
        try:
            lms_cur.execute("SELECT TOP 1 * FROM tblCharter")
            print("Found: tblCharter")
        except:
            try:
                lms_cur.execute("SELECT TOP 1 * FROM Charter")
                print("Found: Charter")
            except:
                try:
                    lms_cur.execute("SELECT TOP 1 * FROM Booking")
                    print("Found: Booking")
                except:
                    print("Cannot find table")

lms_cur.close()
lms_conn.close()
