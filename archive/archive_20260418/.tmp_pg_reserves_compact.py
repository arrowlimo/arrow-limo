import psycopg2
conn=psycopg2.connect(host='localhost',port=5432,dbname='almsdata',user='postgres',password='ArrowLimousine')
reserves=('012144','012237')
cur=conn.cursor()
print('CHARTERS')
cur.execute("""
select charter_id, reserve_number, charter_date, status,
       total_amount_due, payment_totals, balance,
       coalesce(left(notes,120),'') as notes,
       coalesce(left(booking_notes,120),'') as booking_notes,
       coalesce(left(client_notes,120),'') as client_notes,
       coalesce(left(driver_notes,120),'') as driver_notes,
       coalesce(left(calendar_notes,120),'') as calendar_notes,
       payment_id, receipt_id, income_ledger_id, accounting_entry_id,
       paid_amount, amount_paid, balance_owing, grand_total, subtotal, gst_amount
from charters
where reserve_number = any(%s)
order by reserve_number, charter_date, charter_id
""", (list(reserves),))
for row in cur.fetchall():
    print(row)
print('\nINVOICES')
cur.execute("""
select invoice_id, reserve_number, invoice_date, invoice_total, total_payments,
       balance_due, invoice_status, paid, coalesce(left(notes,120),'') as notes
from invoices
where reserve_number = any(%s)
order by reserve_number, invoice_date, invoice_id
""", (list(reserves),))
for row in cur.fetchall():
    print(row)
print('\nPAYMENTS')
cur.execute("""
select payment_id, reserve_number, charter_id, payment_date, amount, payment_amount,
       status, payment_method, coalesce(left(notes,120),'') as notes,
       income_ledger_id, accounting_entry_id, receipt_id
from payments
where reserve_number = any(%s)
order by reserve_number, payment_date, payment_id
""", (list(reserves),))
for row in cur.fetchall():
    print(row)
conn.close()
