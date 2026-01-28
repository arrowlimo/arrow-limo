import psycopg2
import pyodbc
import os

# PostgreSQL connection
pg_conn = psycopg2.connect(
    host=os.environ.get('DB_HOST','localhost'),
    dbname=os.environ.get('DB_NAME','almsdata'),
    user=os.environ.get('DB_USER','postgres'),
    password=os.environ.get('DB_PASSWORD','***REMOVED***')
)
pg_cur = pg_conn.cursor()

# LMS Access connection
LMS_PATH = r'L:\limo\lms.mdb'
try:
    lms_conn_str = f'DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={LMS_PATH};'
    lms_conn = pyodbc.connect(lms_conn_str)
    lms_cur = lms_conn.cursor()
    print(f"Connected to LMS database at {LMS_PATH}")
except Exception as e:
    print(f"Error connecting to LMS: {e}")
    print(f"Attempted path: {LMS_PATH}")
    print("\nCannot verify LMS status without database connection.")
    print("Showing PostgreSQL cancelled charters only...\n")
    lms_conn = None
    lms_cur = None

# Get cancelled charters from PostgreSQL
pg_cur.execute("""
    SELECT c.reserve_number, c.charter_date, cl.client_name, c.cancelled, c.total_amount_due
    FROM charters c
    LEFT JOIN clients cl ON c.client_id = cl.client_id
    WHERE c.cancelled = TRUE
    AND c.reserve_number IS NOT NULL
    ORDER BY c.reserve_number
""")
pg_cancelled = pg_cur.fetchall()

print(f"Found {len(pg_cancelled)} cancelled charters in PostgreSQL")
print("\nChecking LMS for cancellation status...\n")

# Check each in LMS
not_cancelled_in_lms = []

if lms_cur:
    for pg_charter in pg_cancelled:
        reserve_num, charter_date, client_name, is_cancelled, total = pg_charter
        
        # Query LMS
        lms_cur.execute("""
            SELECT Reserve_No, Cancelled, PU_Date, Name, Balance
            FROM Reserve
            WHERE Reserve_No = ?
        """, (reserve_num,))
        
        lms_charter = lms_cur.fetchone()
        
        if lms_charter:
            lms_reserve, lms_cancelled, lms_date, lms_name, lms_balance = lms_charter
            
            # Check if LMS shows not cancelled (False or 0 or NULL)
            if not lms_cancelled:
                not_cancelled_in_lms.append({
                    'reserve_number': reserve_num,
                    'charter_date': charter_date,
                    'client_name': client_name or lms_name,
                    'pg_total': total,
                    'lms_balance': lms_balance
                })
else:
    # Just show all PostgreSQL cancelled charters
    for pg_charter in pg_cancelled:
        reserve_num, charter_date, client_name, is_cancelled, total = pg_charter
        not_cancelled_in_lms.append({
            'reserve_number': reserve_num,
            'charter_date': charter_date,
            'client_name': client_name,
            'pg_total': total,
            'lms_balance': None
        })

print("="*80)
print("CHARTERS CANCELLED IN POSTGRESQL BUT NOT IN LMS")
print("="*80)
print(f"{'Reserve':8} | {'Date':10} | {'Client':25} | {'PG Total':10} | {'LMS Balance':12}")
print("-"*80)

for charter in not_cancelled_in_lms:
    res = charter['reserve_number']
    date = str(charter['charter_date']) if charter['charter_date'] else 'None'
    client = (charter['client_name'] or 'Unknown')[:25]
    pg_total = f"${charter['pg_total']:.2f}" if charter['pg_total'] else "$0.00"
    lms_bal = f"${charter['lms_balance']:.2f}" if charter['lms_balance'] else "$0.00"
    
    print(f"{res:8} | {date:10} | {client:25} | {pg_total:>10} | {lms_bal:>12}")

print("-"*80)
print(f"Total charters to update in LMS: {len(not_cancelled_in_lms)}")

# Generate SQL update statements for LMS
if not_cancelled_in_lms:
    print("\n" + "="*80)
    print("SQL STATEMENTS TO UPDATE LMS (run in Access query window):")
    print("="*80)
    for charter in not_cancelled_in_lms:
        print(f"UPDATE Reserve SET Cancelled = True WHERE Reserve_No = '{charter['reserve_number']}';")

pg_cur.close()
pg_conn.close()
if lms_cur:
    lms_cur.close()
if lms_conn:
    lms_conn.close()
