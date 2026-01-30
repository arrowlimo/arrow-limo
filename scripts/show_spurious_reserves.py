#!/usr/bin/env python3
"""
Show the 26 spurious reserves that exist in database but NOT in legacy LMS.
"""
import pyodbc
import psycopg2
import os

LMS_DB = r"L:\limo\data\lms.mdb"
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REDACTED***")

# Get LMS reserves
lms_conn_str = "Driver={Microsoft Access Driver (*.mdb, *.accdb)};DBQ=" + LMS_DB
lms_conn = pyodbc.connect(lms_conn_str)
lms_cur = lms_conn.cursor()

lms_cur.execute("SELECT Reserve_No FROM Reserve WHERE Reserve_No IS NOT NULL")
lms_reserves = {str(row[0]).strip() for row in lms_cur.fetchall()}
lms_conn.close()

# Get database reserves with details
conn = psycopg2.connect(host="localhost", dbname="almsdata", user="postgres", password=DB_PASSWORD)
cur = conn.cursor()

cur.execute("""
    SELECT c.reserve_number, cl.name as client_name, c.charter_date, COUNT(*) as charter_count
    FROM charters c
    LEFT JOIN clients cl ON cl.client_id = c.client_id
    GROUP BY c.reserve_number, cl.name, c.charter_date
    ORDER BY c.reserve_number
""")

spurious = []
for row in cur.fetchall():
    res_num = row[0]
    if res_num not in lms_reserves:
        spurious.append({
            'reserve': res_num,
            'client': row[1] or "NULL",
            'date': row[2],
            'count': row[3]
        })

print("=" * 100)
print("26 SPURIOUS RESERVES (IN DATABASE BUT NOT IN LMS)")
print("=" * 100)
print(f"\n{'Reserve':<10} {'Client Name':<35} {'Charter Date':<12} {'Count':<6}")
print("-" * 100)

for item in spurious:
    print(f"{item['reserve']:<10} {item['client']:<35} {str(item['date']):<12} {item['count']:<6}")

print("\n" + "=" * 100)
print(f"TOTAL SPURIOUS RESERVES: {len(spurious)}")
print("=" * 100)

# Summary
if spurious:
    dates = set(str(item['date']) for item in spurious)
    print(f"\nAll spurious reserves share same date(s): {', '.join(sorted(dates))}")
    print("These appear to be auto-generated placeholder records.")
    print("\nRecommendation: Keep them (don't delete) as per user request.")

cur.close()
conn.close()
