#!/usr/bin/env python3
"""Check if missing reserves are new/recent charters."""
import pyodbc

LMS_PATH = r'L:\limo\database_backups\lms2026.mdb'

# List of reserves missing from ALMS
missing = [1000, 1820, 2836, 3443, 3453, 5558, 6459, 6629, 6789, 6799, 6944, 
           7309, 7482, 8290, 8299, 8502, 8531, 8648, 8763, 9073, 9215, 9261,
           9351, 9493, 9563, 9617, 9723, 9893, 10045, 10152, 10358, 10517,
           10634, 10786, 10999, 11134, 11271, 11442, 11599, 11748, 11899,
           12052, 12199, 12347, 12495, 12643, 12791, 12939]

conn = pyodbc.connect(f'Driver={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={LMS_PATH};')
cur = conn.cursor()

# Check first 10 individually
for reserve_no in missing[:10]:
    cur.execute('SELECT Reserve_No, PU_Date, [Closed], [Cancelled] FROM Reserve WHERE Reserve_No = ?', (reserve_no,))
    row = cur.fetchone()
    if row:
        reserve = str(row[0]).zfill(6)
        pickup = row[1] if row[1] else "No date"
        closed = "Yes" if row[2] else "No"
        cancelled = "Yes" if row[3] else "No"
        print(f"{reserve} | {pickup} | {closed:6} | {cancelled}")
    else:
        print(f"{str(reserve_no).zfill(6)} | NOT IN LMS RESERVE TABLE")

print("Reserve | Pickup_Date        | Closed | Cancelled")
print("-" * 60)
for row in cur.fetchall():
    reserve = str(row[0]).zfill(6)
    pickup = row[1]
    closed = "Yes" if row[2] else "No"
    cancelled = "Yes" if row[3] else "No"
    print(f"{reserve} | {pickup} | {closed:6} | {cancelled}")

conn.close()
