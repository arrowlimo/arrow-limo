#!/usr/bin/env python3
"""
Find last charter in almsdata and check what needs to be added from LMS.
"""

import psycopg2
import pyodbc

DB_HOST = "localhost"
DB_NAME = "almsdata"
DB_USER = "postgres"
DB_PASSWORD = "***REMOVED***"

LMS_PATH = r"L:\limo\backups\lms.mdb"

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

print("=" * 90)
print("FINDING LAST CHARTER IN ALMSDATA AND COMPARING TO LMS")
print("=" * 90)
print()

# Get last charter in almsdata
cur.execute("""
    SELECT reserve_number, charter_date
    FROM charters
    ORDER BY charter_date DESC, reserve_number DESC
    LIMIT 1
""")

row = cur.fetchone()
if row:
    last_alms_reserve, last_alms_date = row
    print(f"Last charter in almsdata: {last_alms_reserve} ({last_alms_date})")
else:
    print("No charters in almsdata")
    cur.close()
    conn.close()
    exit(1)

print()

# Connect to LMS and count charters
lms_conn_str = f"Driver={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={LMS_PATH};"
lms_conn = pyodbc.connect(lms_conn_str)
lms_cur = lms_conn.cursor()

try:
    # Get field names first
    lms_cur.execute("SELECT TOP 1 * FROM Reservation")
    cols = [d[0] for d in lms_cur.description] if lms_cur.description else []
    
    reserve_field = None
    date_field = None
    for col in cols:
        cl = col.lower()
        if "reserve" in cl and ("no" in cl or "id" in cl):
            reserve_field = col
        if "date" in cl and ("charter" in cl or "svc" in cl or "event" in cl):
            date_field = col
    
    print(f"LMS fields found: ReserveID={reserve_field}, DateField={date_field}")
    print()
    
    # Get total count in LMS
    lms_cur.execute("SELECT COUNT(*) FROM Reservation")
    total_lms = lms_cur.fetchone()[0]
    
    # Get total count in almsdata
    cur.execute("SELECT COUNT(*) FROM charters")
    total_alms = cur.fetchone()[0]
    
    print(f"Total charters in LMS: {total_lms}")
    print(f"Total charters in almsdata: {total_alms}")
    print(f"Difference: {total_lms - total_alms} charters to add")
    print()
    
    # Get last charter in LMS
    if reserve_field and date_field:
        query = f"SELECT TOP 1 [{reserve_field}], [{date_field}] FROM Reservation ORDER BY [{date_field}] DESC, [{reserve_field}] DESC"
        lms_cur.execute(query)
        lms_row = lms_cur.fetchone()
        
        if lms_row:
            last_lms_reserve, last_lms_date = lms_row
            print(f"Last charter in LMS: {last_lms_reserve} ({last_lms_date})")
            print()
            
            # Get charters in LMS after last almsdata charter
            query = f"SELECT COUNT(*) FROM Reservation WHERE [{date_field}] > ?"
            lms_cur.execute(query, (last_alms_date,))
            newer_count = lms_cur.fetchone()[0]
            
            print(f"Charters in LMS after {last_alms_date}: {newer_count}")

except Exception as e:
    print(f"Error: {e}")

lms_cur.close()
lms_conn.close()
cur.close()
conn.close()
