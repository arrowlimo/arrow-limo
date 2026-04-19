import psycopg2
from psycopg2.extras import RealDictCursor

conn = psycopg2.connect("dbname=almsdata user=postgres host=localhost password=ArrowLimousine")
cur = conn.cursor(cursor_factory=RealDictCursor)

# Check reserve 001822
cur.execute("""
SELECT 
  reserve_number,
  charter_date,
  grand_total,
  paid_amount,
  balance_owing,
  notes,
  cancelled,
  charter_type
FROM charters
WHERE reserve_number = '001822'
""")

row = cur.fetchone()
if row:
    print("001822 in almsdata:")
    for k, v in row.items():
        print(f"  {k}: {v}")
        
    # Check charges
    cur.execute("""
    SELECT charge_id, description, amount
    FROM charter_charges
    WHERE reserve_number = '001822'
    ORDER BY charge_id
    """)
    charges = cur.fetchall()
    print(f"\n  Charges: {len(charges)} rows")
    for c in charges:
        print(f"    {c['charge_id']}: {c['description']} = ${c['amount']}")
else:
    print("001822: NOT FOUND")

# Also check LMS
import pyodbc
LMS_PATH = r"l:\lms2026c.mdb"
conn_str = rf"Driver={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={LMS_PATH};"
lms_conn = pyodbc.connect(conn_str)
lms_cur = lms_conn.cursor()

lms_cur.execute(f"SELECT Res_No, Res_Type, Res_Status, ChargeAmt FROM Reserve WHERE Res_No = '001822'")
lms_row = lms_cur.fetchone()
if lms_row:
    print(f"\n001822 in LMS:")
    print(f"  Res_Type: {lms_row.Res_Type}")
    print(f"  Res_Status: {lms_row.Res_Status}")
    print(f"  ChargeAmt: {lms_row.ChargeAmt}")
else:
    print(f"\n001822 in LMS: NOT FOUND")

lms_conn.close()
conn.close()
