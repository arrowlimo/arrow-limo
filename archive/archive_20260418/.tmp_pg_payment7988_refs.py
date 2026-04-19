import psycopg2
conn=psycopg2.connect(host='localhost',port=5432,dbname='almsdata',user='postgres',password='ArrowLimousine')
cur=conn.cursor()
print('PAYMENT 7988')
cur.execute("""
select payment_id, reserve_number, charter_id, amount, payment_amount, payment_date, status,
       payment_method, notes, receipt_id, income_ledger_id, accounting_entry_id,
       related_payment_id, reference_number, payment_key
from payments
where payment_id=7988
""")
for row in cur.fetchall():
    print(row)

queries = {
'charter_payments': "select * from charter_payments where payment_id=7988 order by id",
'income_ledger': "select * from income_ledger where payment_id=7988 order by income_id",
'accounting_entries': "select * from accounting_entries where payment_id=7988 order by id",
'receipts': "select * from receipts where payment_id=7988 order by receipt_id",
'charters_by_payment_id': "select charter_id,reserve_number,charter_date,status,total_amount_due,payment_totals,balance,payment_id,receipt_id,income_ledger_id,accounting_entry_id from charters where payment_id=7988 order by charter_id",
'payments_related_payment_id': "select payment_id,reserve_number,amount,payment_date,status,related_payment_id,reference_number,payment_key from payments where related_payment_id=7988 order by payment_id",
'payments_reference_number': "select payment_id,reserve_number,amount,payment_date,status,related_payment_id,reference_number,payment_key from payments where coalesce(reference_number,'') like '%7988%' or coalesce(payment_key,'') like '%7988%' order by payment_id"
}
for name,q in queries.items():
    print(f'\n{name.upper()}')
    cur.execute(q)
    rows=cur.fetchall()
    print(f'count={len(rows)}')
    for row in rows:
        print(row)
conn.close()
