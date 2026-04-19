import psycopg2
from psycopg2.extras import RealDictCursor
conn=psycopg2.connect(dbname='almsdata', user='postgres', password='ArrowLimousine', host='localhost', port=5432)
cur=conn.cursor(cursor_factory=RealDictCursor)
for tid in (60511,96010,100158,100159,100164):
    cur.execute("SELECT transaction_id, account_number, transaction_date, debit_amount, description, source_file, import_batch, receipt_id FROM banking_transactions WHERE transaction_id=%s", (tid,))
    print('\nBT', dict(cur.fetchone()))
    cur.execute("SELECT receipt_id, receipt_date, vendor_name, gross_amount, receipt_source, gl_account_code, gl_code, exclude_from_reports FROM receipts WHERE banking_transaction_id=%s ORDER BY receipt_id", (tid,))
    rs=cur.fetchall(); print('receipts',len(rs))
    for r in rs: print(dict(r))
cur.close(); conn.close()
