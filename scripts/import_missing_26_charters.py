"""
Import 26 missing charters from LMS that weren't caught by incremental sync
These charters exist in LMS with LastUpdated dates but aren't in PostgreSQL
"""
import pyodbc
import psycopg2
from psycopg2.extras import RealDictCursor
import os
import sys

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***')
    )

# Connect to LMS
LMS_PATH = r'L:\limo\backups\lms.mdb'
try:
    conn_str = f'DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={LMS_PATH};'
    lms_conn = pyodbc.connect(conn_str)
except:
    conn_str = f'DRIVER={{Microsoft Access Driver (*.mdb)}};DBQ={LMS_PATH};'
    lms_conn = pyodbc.connect(conn_str)

lms_cur = lms_conn.cursor()

# Connect to PostgreSQL
conn = get_db_connection()
cur = conn.cursor(cursor_factory=RealDictCursor)

missing_reserves = ['013305', '017186', '019572', '019627', '019628', '019629', '019634', '019635',
                    '019636', '019637', '019640', '019642', '019646', '019647', '019648', '019649',
                    '019650', '019653', '019654', '019656', '019659', '019661', '019662', '019663',
                    '019667', '019668']

print("=" * 100)
print("IMPORTING 26 MISSING CHARTERS FROM LMS")
print("=" * 100)

# Check if --write flag provided
write_mode = '--write' in sys.argv

if not write_mode:
    print("\n⚠️  DRY RUN MODE - No changes will be made")
    print("   Run with --write to apply changes\n")

inserted = 0
skipped = 0

for reserve_no in sorted(missing_reserves):
    # Get full charter data from LMS
    lms_cur.execute("""
    SELECT *
    FROM Reserve
    WHERE Reserve_No = ?
    """, (reserve_no,))
    
    row = lms_cur.fetchone()
    if not row:
        print(f"✗ {reserve_no}: Not found in LMS")
        skipped += 1
        continue
    
    # Check if already exists in PostgreSQL
    cur.execute("SELECT charter_id FROM charters WHERE reserve_number = %s", (reserve_no,))
    existing = cur.fetchone()
    
    if existing:
        print(f"⊙ {reserve_no}: Already exists in PostgreSQL (charter_id={existing['charter_id']})")
        skipped += 1
        continue
    
    # Prepare insert
    charter_date = row.PU_Date
    est_charge = float(row.Est_Charge) if row.Est_Charge else 0
    rate = float(row.Rate) if row.Rate else 0
    balance = float(row.Balance) if row.Balance else 0
    deposit = float(row.Deposit) if row.Deposit else 0
    
    print(f"✓ {reserve_no}: {charter_date} | {row.Name or 'Unknown'} | ${est_charge:,.2f}")
    
    if write_mode:
        try:
            cur.execute("""
                INSERT INTO charters (
                    reserve_number, account_number, charter_date, pickup_time,
                    rate, total_amount_due, balance, deposit, 
                    vehicle, driver, status, notes, created_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
            """, (
                reserve_no,
                row.Account_No,
                charter_date,
                row.PU_Time,
                rate,
                est_charge,  # total_amount_due = Est_Charge
                balance,
                deposit,
                row.Vehicle,
                row.Driver,
                row.Status,
                row.Notes
            ))
            inserted += 1
        except Exception as e:
            print(f"  ✗ Error inserting: {e}")
            skipped += 1

print("\n" + "=" * 100)
print("SUMMARY")
print("=" * 100)
print(f"\nCharters to import: {len(missing_reserves)}")
print(f"Successfully imported: {inserted}")
print(f"Skipped: {skipped}")

if write_mode:
    conn.commit()
    print(f"\n✓ Changes committed to database")
else:
    print(f"\n⚠️  DRY RUN - No changes made. Run with --write to apply.")

cur.close()
conn.close()
lms_cur.close()
lms_conn.close()
