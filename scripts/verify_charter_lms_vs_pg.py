"""
Verify charter records from LMS backup (Access DB) vs current almsdata.
Using 'Reserve' table (not 'Charter').
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
pg_conn = psycopg2.connect(host='localhost', dbname='almsdata', user='postgres', password='***REDACTED***')
pg_cur = pg_conn.cursor()

# Check Reserve table columns
lms_cur.execute("SELECT * FROM Reserve WHERE 1=0")
columns = [desc[0] for desc in lms_cur.description]
print(f"Reserve table columns: {columns}\n")

# Sample some reserves to compare
print("📋 Comparing LMS vs PostgreSQL charter data (charter date = pickup date):\n")
print("=" * 120)

# Get sample reserves from LMS
lms_cur.execute("""
    SELECT TOP 10 Reserve_No, Driver, PU_Date
    FROM Reserve
    WHERE Reserve_No IS NOT NULL
    ORDER BY PU_Date DESC
""")

lms_data = lms_cur.fetchall()

for lms_row in lms_data:
    lms_reserve = str(lms_row[0]).strip()
    lms_driver = lms_row[1]
    lms_pu_date = lms_row[2]  # Charter date (pickup date)
    
    # Find in PostgreSQL
    pg_cur.execute("""
        SELECT reserve_number, employee_id, charter_date
        FROM charters
        WHERE reserve_number = %s
    """, (lms_reserve,))
    
    pg_row = pg_cur.fetchone()
    
    if pg_row:
        pg_reserve, pg_emp_id, pg_charter_date = pg_row
        status = "✅"
        
        # Check if charter dates match
        date_match = str(lms_pu_date)[:10] == str(pg_charter_date)[:10]
        if not date_match:
            status = "⚠️  DATE MISMATCH"
        
        print(f"{status} Reserve {lms_reserve}")
        print(f"   LMS:  Driver='{lms_driver}', Charter Date (PU_Date)={lms_pu_date}")
        print(f"   PG:   employee_id={pg_emp_id}, charter_date={pg_charter_date}")
    else:
        print(f"❌ Reserve {lms_reserve} NOT FOUND in PostgreSQL")
        print(f"   LMS: Driver='{lms_driver}', Charter Date (PU_Date)={lms_pu_date}")
    
    print()

print("=" * 120)

lms_cur.close()
lms_conn.close()
pg_cur.close()
pg_conn.close()

print("\n✅ Verification complete")
