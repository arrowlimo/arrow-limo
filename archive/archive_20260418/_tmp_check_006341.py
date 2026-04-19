import psycopg2
import pyodbc

PG = dict(host='localhost', port=5432, dbname='almsdata', user='postgres', password='ArrowLimousine')
LMS = r"L:\lms2026b.mdb"
RES = '006341'

pg = psycopg2.connect(**PG)
cur = pg.cursor()

cur.execute("""
SELECT reserve_number, charter_date, grand_total, payment_totals, balance, client_display_name
FROM charters
WHERE reserve_number=%s
""", (RES,))
print('ALMS charter before:')
for r in cur.fetchall():
    print(r)

cur.execute("""
SELECT id, charter_id, amount, payment_date, payment_method, COALESCE(payment_key,''), source, COALESCE(client_name,'')
FROM charter_payments
WHERE charter_id=%s
ORDER BY payment_date NULLS LAST, id
""", (RES,))
print('\nALMS payments before:')
for r in cur.fetchall():
    print(r)

lms = pyodbc.connect(f"DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={LMS};")
lcur = lms.cursor()
lcur.execute("SELECT Reserve_No, Amount, [Key], LastUpdated, LastUpdatedBy FROM Payment WHERE Reserve_No=? ORDER BY LastUpdated, [Key]", (RES,))
print('\nLMS payments:')
for r in lcur.fetchall():
    print(r)

cur.close(); pg.close(); lcur.close(); lms.close()
