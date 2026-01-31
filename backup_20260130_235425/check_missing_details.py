#!/usr/bin/env python3
"""Check 66 missing reserves in LMS database."""
import pyodbc
import psycopg2
import os

LMS_DB = r"L:\limo\data\lms.mdb"
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REDACTED***")

# Connect to both databases
lms_conn_str = "Driver={Microsoft Access Driver (*.mdb, *.accdb)};DBQ=" + LMS_DB
lms_conn = pyodbc.connect(lms_conn_str)
lms_cur = lms_conn.cursor()

# Get all LMS reserves
lms_cur.execute("SELECT Reserve_No FROM Reserve WHERE Reserve_No IS NOT NULL")
lms_reserves = {str(row[0]).strip() for row in lms_cur.fetchall()}

# Get database reserves
conn = psycopg2.connect(host="localhost", dbname="almsdata", user="postgres", password=DB_PASSWORD)
cur = conn.cursor()

cur.execute("SELECT DISTINCT reserve_number FROM charters WHERE reserve_number IS NOT NULL")
db_reserves = {row[0] for row in cur.fetchall()}

# Find missing
missing = sorted(lms_reserves - db_reserves)

print(f"Total missing reserves: {len(missing)}")
print(f"\nMissing reserves: {', '.join(missing)}")

# Now get details for each missing reserve
print("\n" + "=" * 100)
print("DETAILED INFO ON MISSING RESERVES")
print("=" * 100)
print(f"{'Reserve':<8} | {'Client Name':<30} | {'PU_Date':<20} | {'Order_Date':<20}")
print("-" * 100)

for res_no in missing:
    lms_cur.execute(f"SELECT Name, PU_Date, Order_Date FROM Reserve WHERE Reserve_No = '{res_no}'")
    row = lms_cur.fetchone()
    if row:
        client = str(row[0]).strip() if row[0] else "NULL"
        pu_date = row[1] if row[1] else "NULL"
        order_date = row[2] if row[2] else "NULL"
        print(f"{res_no:<8} | {client:<30} | {str(pu_date):<20} | {str(order_date):<20}")

# Statistics
lms_cur.execute("SELECT MIN(PU_Date), MAX(PU_Date) FROM Reserve WHERE Reserve_No IN (" + 
                ",".join([f"'{r}'" for r in missing]) + ")")
min_max = lms_cur.fetchone()

print("\n" + "=" * 100)
print("SUMMARY")
print("=" * 100)
if min_max and min_max[0]:
    print(f"Date range of missing reserves:")
    print(f"  Earliest PU_Date: {min_max[0]}")
    print(f"  Latest PU_Date:   {min_max[1]}")
    
    # Check if recent
    from datetime import datetime
    earliest_year = min_max[0].year if hasattr(min_max[0], 'year') else 0
    print(f"\nAll missing reserves are from {earliest_year}? Check above.")
else:
    print("No date information found for missing reserves")

lms_conn.close()
cur.close()
conn.close()
