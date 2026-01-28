"""
Verify charter records from LMS backup (Access DB) vs current almsdata.
"""
import pyodbc
import psycopg2

# Connect to LMS backup (Access)
lms_conn_str = r'Driver={Microsoft Access Driver (*.mdb, *.accdb)};DBQ=L:\limo\backups\lms.mdb;'
try:
    lms_conn = pyodbc.connect(lms_conn_str)
    lms_cur = lms_conn.cursor()
    print("✅ Connected to LMS.mdb backup\n")
except Exception as e:
    print(f"❌ Failed to connect to LMS.mdb: {e}")
    exit(1)

# Connect to current PostgreSQL database
pg_conn = psycopg2.connect(host='localhost', dbname='almsdata', user='postgres', password='***REMOVED***')
pg_cur = pg_conn.cursor()

# Sample some reserves to compare
print("📋 Comparing LMS vs PostgreSQL charter data:\n")
print("=" * 100)

# Get sample reserves from LMS
lms_cur.execute("""
    SELECT TOP 10 Reserve_No, Driver_ID, Driver_Name, Date_of_Charter
    FROM Charter
    WHERE Reserve_No IS NOT NULL
    ORDER BY Date_of_Charter DESC
""")

lms_data = lms_cur.fetchall()

for lms_row in lms_data:
    lms_reserve = str(lms_row[0]).strip()
    lms_driver_id = lms_row[1]
    lms_driver_name = lms_row[2]
    lms_date = lms_row[3]
    
    # Find in PostgreSQL
    pg_cur.execute("""
        SELECT reserve_number, employee_id, driver_name, charter_date
        FROM charters
        WHERE reserve_number = %s
    """, (lms_reserve,))
    
    pg_row = pg_cur.fetchone()
    
    if pg_row:
        pg_reserve, pg_emp_id, pg_driver_name, pg_date = pg_row
        status = "✅"
        
        # Check if dates match
        if str(lms_date) != str(pg_date):
            status = "⚠️  DATE MISMATCH"
        
        print(f"{status} Reserve {lms_reserve}")
        print(f"   LMS:  driver_id={lms_driver_id}, name='{lms_driver_name}', date={lms_date}")
        print(f"   PG:   employee_id={pg_emp_id}, driver_name='{pg_driver_name}', date={pg_date}")
    else:
        print(f"❌ Reserve {lms_reserve} NOT FOUND in PostgreSQL")
        print(f"   LMS: driver_id={lms_driver_id}, name='{lms_driver_name}', date={lms_date}")
    
    print()

print("=" * 100)

lms_cur.close()
lms_conn.close()
pg_cur.close()
pg_conn.close()

print("\n✅ Verification complete")
