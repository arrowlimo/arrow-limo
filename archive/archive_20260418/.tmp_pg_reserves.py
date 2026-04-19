import psycopg2
from psycopg2.extras import RealDictCursor
conn=psycopg2.connect(host='localhost',port=5432,dbname='almsdata',user='postgres',password='ArrowLimousine')
reserves=('012144','012237')
cur=conn.cursor(cursor_factory=RealDictCursor)
print('CHARTERS')
cur.execute("""
select charter_id, reserve_number, charter_date, status,
       total_amount_due, payment_totals, balance,
       notes, booking_notes, client_notes, driver_notes, calendar_notes,
       payment_id, receipt_id, income_ledger_id, accounting_entry_id,
       paid_amount, amount_paid, balance_owing, grand_total, subtotal, gst_amount
from charters
where reserve_number = any(%s)
order by reserve_number, charter_date, charter_id
""", (list(reserves),))
for row in cur.fetchall():
    print(dict(row))
print('\nINVOICES')
cur.execute("""
select invoice_id, reserve_number, invoice_date, invoice_total as invoice_amount, total_payments as payment_totals,
       balance_due as balance, invoice_status as status, paid, notes
from invoices
where reserve_number = any(%s)
order by reserve_number, invoice_date, invoice_id
""", (list(reserves),))
for row in cur.fetchall():
    print(dict(row))
print('\nPAYMENTS')
cur.execute("""
select payment_id, reserve_number, charter_id, payment_date, amount, payment_amount,
       status, payment_method, notes, income_ledger_id, accounting_entry_id, receipt_id
from payments
where reserve_number = any(%s)
order by reserve_number, payment_date, payment_id
""", (list(reserves),))
for row in cur.fetchall():
    print(dict(row))
conn.close()
