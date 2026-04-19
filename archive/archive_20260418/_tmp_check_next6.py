import psycopg2
import pyodbc

reserves = ['014466','014468','014469','015275','016042','016107']

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
    for r in cur.fetchall():
        print(r)

    cur.execute("""
    SELECT c.reserve_number, cc.sequence, cc.charge_type, cc.description, cc.amount
    FROM charters c JOIN charter_charges cc ON cc.charter_id=c.charter_id
    WHERE c.reserve_number=%s
    ORDER BY cc.sequence, cc.charge_id
    """, (res,))
    print('ALMS charges:')
    for r in cur.fetchall():
        print(r)

    lcur.execute("SELECT Reserve_No, Amount, [Key], LastUpdated, LastUpdatedBy FROM Payment WHERE Reserve_No=? ORDER BY LastUpdated, [Key]", (res,))
    print('LMS payments:')
    for r in lcur.fetchall():
        print(r)

cur.close(); pg.close(); lcur.close(); lms.close()
