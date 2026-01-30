"""Restore missing charter dates from LMS database"""
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
    password="***REDACTED***"
)
pg_cur = pg_conn.cursor()

# Get the 23 charters with NULL dates
pg_cur.execute("""
    SELECT reserve_number
    FROM charters 
    WHERE charter_date IS NULL
    ORDER BY reserve_number
""")

null_date_charters = [row[0] for row in pg_cur.fetchall()]

print(f"\n{'='*80}")
print(f"RESTORING DATES FOR {len(null_date_charters)} CHARTERS FROM LMS")
print(f"{'='*80}\n")

restored = 0
errors = 0

for res_num in null_date_charters:
    try:
        # Get date from LMS
        lms_cur.execute("""
            SELECT Reserve_No, PU_Date
            FROM Reserve
            WHERE Reserve_No = ?
        """, (res_num,))
        
        lms_row = lms_cur.fetchone()
        
        if lms_row and lms_row[1]:
            lms_reserve_no, lms_date = lms_row
            
            # Update PostgreSQL
            pg_cur.execute("""
                UPDATE charters
                SET charter_date = %s,
                    updated_at = NOW()
                WHERE reserve_number = %s
            """, (lms_date, res_num))
            
            print(f"✅ {res_num}: Set charter_date to {lms_date}")
            restored += 1
        else:
            print(f"⚠️  {res_num}: Not found in LMS or LMS date is NULL")
            errors += 1
    
    except Exception as e:
        print(f"❌ {res_num}: Error - {e}")
        errors += 1

# Commit changes
pg_conn.commit()

print(f"\n{'='*80}")
print(f"SUMMARY:")
print(f"{'='*80}")
print(f"Successfully restored: {restored}")
print(f"Errors: {errors}")
print(f"✅ Changes committed to database")

# Verify the fix
pg_cur.execute("""
    SELECT COUNT(*)
    FROM charters 
    WHERE charter_date IS NULL
""")

remaining_null = pg_cur.fetchone()[0]
print(f"\nRemaining charters with NULL dates: {remaining_null}")

if remaining_null == 0:
    print("🎉 SUCCESS! All charter dates have been restored!")

lms_cur.close()
lms_conn.close()
pg_cur.close()
pg_conn.close()
