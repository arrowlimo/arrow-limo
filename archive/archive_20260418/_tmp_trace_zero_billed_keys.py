import pyodbc
import psycopg2
import psycopg2.extras

LMS = r"L:\lms2026c.mdb"
PG = "host=localhost port=5432 dbname=almsdata user=postgres password=ArrowLimousine"
TARGETS = ['013603', '014215', '001188', '001918', '013963']

pg = psycopg2.connect(PG)
cur = pg.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
cur.execute("""
SELECT id, charter_id, amount, payment_date, payment_key, source
FROM charter_payments
WHERE charter_id = ANY(%s)
ORDER BY charter_id, id
""", (TARGETS,))
rows = cur.fetchall()
keys = sorted({(r['payment_key'] or '').strip() for r in rows if (r['payment_key'] or '').strip()})
print('Target ALMS keys:', keys)

# show where those keys appear in ALMS overall
for k in keys:
    cur.execute("""
    SELECT charter_id, COUNT(*) AS cnt, SUM(amount) AS tot
    FROM charter_payments
    WHERE payment_key = %s
    GROUP BY charter_id
    ORDER BY charter_id
    """, (k,))
    print(f"\nALMS key {k} usage:")
    for x in cur.fetchall():
        print(' ', x['charter_id'], 'cnt=', x['cnt'], 'tot=', x['tot'])
pg.close()

# LMS side for same keys
lms = pyodbc.connect(f"DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={LMS};")
lcur = lms.cursor()
for k in keys:
    lcur.execute("SELECT Reserve_No, Amount, [Key], LastUpdated FROM Payment WHERE [Key]=? ORDER BY Reserve_No, LastUpdated", (k,))
    res = lcur.fetchall()
    print(f"\nLMS key {k} rows:")
    if not res:
        print('  (none)')
    for r in res:
        print(' ', str(r.Reserve_No).zfill(6), 'amt=', r.Amount, 'date=', r.LastUpdated)

lms.close()
