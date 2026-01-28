"""Verify charter dates in legacy LMS database for the 23 NULL date charters"""
import pyodbc
import psycopg2
from datetime import datetime

# Connect to LMS (Access database)
LMS_PATH = r"L:\limo\backups\lms.mdb"
lms_conn = pyodbc.connect(
    r'Driver={Microsoft Access Driver (*.mdb, *.accdb)};'
    f'DBQ={LMS_PATH};'
)
lms_cur = lms_conn.cursor()

# Connect to PostgreSQL
pg_conn = psycopg2.connect(
    host="localhost",
    database="almsdata",
    user="postgres",
    password="***REMOVED***"
)
pg_cur = pg_conn.cursor()

# Get the 23 charters with NULL dates from PostgreSQL
pg_cur.execute("""
    SELECT reserve_number, booking_status, total_amount_due, created_at
    FROM charters 
    WHERE charter_date IS NULL
    ORDER BY reserve_number
""")

null_date_charters = pg_cur.fetchall()

print(f"\n{'='*100}")
print(f"VERIFYING {len(null_date_charters)} CHARTERS WITH NULL DATES IN LMS DATABASE")
print(f"{'='*100}\n")

found_in_lms = 0
not_found_in_lms = 0
lms_has_date = 0
lms_also_null = 0

for res_num, status, total, created in null_date_charters:
    # Query LMS database
    try:
        lms_cur.execute("""
            SELECT Reserve_No, PU_Date, Status, Est_Charge
            FROM Reserve
            WHERE Reserve_No = ?
        """, (res_num,))
        
        lms_row = lms_cur.fetchone()
        
        if lms_row:
            found_in_lms += 1
            lms_reserve_no, lms_date, lms_status, lms_total = lms_row
            
            print(f"Reserve: {res_num}")
            print(f"  PostgreSQL: charter_date=NULL, status={status}, total=${total:.2f}")
            print(f"  LMS:        charter_date={lms_date}, status={lms_status}, total=${lms_total:.2f}")
            
            if lms_date:
                lms_has_date += 1
                print(f"  ⚠️  LMS HAS A DATE BUT POSTGRESQL IS NULL - DATA LOSS DURING IMPORT!")
            else:
                lms_also_null += 1
                print(f"  ✅ LMS also has NULL/empty date")
            
            print()
        else:
            not_found_in_lms += 1
            print(f"Reserve: {res_num}")
            print(f"  ❌ NOT FOUND IN LMS DATABASE")
            print(f"     Created in PostgreSQL: {created}")
            print()
    
    except Exception as e:
        print(f"Reserve: {res_num} - Error querying LMS: {e}\n")

print(f"\n{'='*100}")
print(f"SUMMARY:")
print(f"{'='*100}")
print(f"Total charters checked: {len(null_date_charters)}")
print(f"Found in LMS: {found_in_lms}")
print(f"Not found in LMS: {not_found_in_lms}")
print(f"LMS has valid date (import lost data): {lms_has_date}")
print(f"LMS also has NULL/empty date: {lms_also_null}")

if lms_has_date > 0:
    print(f"\n⚠️  WARNING: {lms_has_date} charters lost their dates during import!")
    print(f"   These should be restored from LMS data.")

lms_cur.close()
lms_conn.close()
pg_cur.close()
pg_conn.close()
