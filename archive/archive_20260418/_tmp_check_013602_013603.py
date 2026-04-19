import pyodbc
import psycopg2
import psycopg2.extras
from decimal import Decimal

LMS = r"L:\lms2026c.mdb"
PG = "host=localhost port=5432 dbname=almsdata user=postgres password=ArrowLimousine"
RES = ['013602','013603']

print('=== LMS ===')
conn = pyodbc.connect(f"DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={LMS};")
cur = conn.cursor()
for r in RES:
    cur.execute("""
    SELECT Reserve_No, Name, Account_No, PU_Date, Cancelled, Est_Charge, Balance
    FROM Reserve
    WHERE Reserve_No = ?
    """, (r,))
    row = cur.fetchone()
    print('Reserve', r, ':', row)

    cur.execute("""
    SELECT Amount, [Key], LastUpdated
    FROM Payment
    WHERE Reserve_No = ?
    ORDER BY LastUpdated, Amount
    """, (r,))
    pays = cur.fetchall()
    tot = sum([Decimal(str(x.Amount or 0)) for x in pays], Decimal('0'))
    print('  payments total=', tot, 'rows=', len(pays))
    for p in pays:
        print('   ', p)
conn.close()

print('\n=== ALMSDATA ===')
pg = psycopg2.connect(PG)
cur = pg.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

cur.execute("""
SELECT reserve_number, charter_date, client_display_name, cancelled, grand_total, balance_owing
FROM charters
WHERE reserve_number = ANY(%s)
ORDER BY reserve_number
""", (RES,))
for r in cur.fetchall():
    print('charter:', r)

cur.execute("""
SELECT id, charter_id, amount, payment_date, payment_key, source
FROM charter_payments
WHERE charter_id = ANY(%s)
   OR payment_key IN ('0015571','0015572')
ORDER BY id
""", (RES,))
rows = cur.fetchall()
for r in rows:
    print('payment:', r)

# totals by reserve
cur.execute("""
WITH p AS (
  SELECT charter_id, SUM(amount) AS paid
  FROM charter_payments
  WHERE charter_id IN ('013602','013603')
  GROUP BY charter_id
)
SELECT c.reserve_number, c.grand_total, COALESCE(p.paid,0) AS paid,
       (COALESCE(c.grand_total,0)-COALESCE(p.paid,0)) AS bal
FROM charters c
LEFT JOIN p ON p.charter_id = c.reserve_number
WHERE c.reserve_number IN ('013602','013603')
ORDER BY c.reserve_number
""")
print('\nTotals by reserve:')
for r in cur.fetchall():
    print(r)

pg.close()
