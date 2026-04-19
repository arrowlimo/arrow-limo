import psycopg2
import pyodbc

reserves = ['019538','018257','017943','018331','018332','018334','018335']

pg = psycopg2.connect(host='localhost', port=5432, dbname='almsdata', user='postgres', password='ArrowLimousine')
cur = pg.cursor()
lms = pyodbc.connect(r"DRIVER={Microsoft Access Driver (*.mdb, *.accdb)};DBQ=L:\lms2026b.mdb;")
lcur = lms.cursor()

for res in reserves:
    print('\n' + '='*90)
    print('RESERVE', res)

    cur.execute("""
    SELECT reserve_number, charter_date, grand_total, total_amount_due, payment_totals, balance, balance_owing,
           paid_amount, amount_paid, client_display_name
    FROM charters WHERE reserve_number=%s
    """, (res,))
    print('ALMS charter:')
    for r in cur.fetchall():
        print(r)

    cur.execute("""
    SELECT id, amount, payment_date, payment_method, COALESCE(payment_key,''), source, COALESCE(client_name,'')
    FROM charter_payments
    WHERE charter_id=%s
    ORDER BY payment_date NULLS LAST, id
    """, (res,))
    print('ALMS payments:')
    alms_rows = cur.fetchall()
    for r in alms_rows:
        print(r)

    lcur.execute("SELECT Reserve_No, Amount, [Key], LastUpdated, LastUpdatedBy FROM Payment WHERE Reserve_No=? ORDER BY LastUpdated, [Key]", (res,))
    print('LMS payments:')
    lms_rows = lcur.fetchall()
    for r in lms_rows:
        print(r)

cur.close(); pg.close(); lcur.close(); lms.close()
