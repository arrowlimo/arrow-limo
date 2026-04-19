import psycopg2
from psycopg2.extras import RealDictCursor
conn=psycopg2.connect(dbname='almsdata', user='postgres', password='ArrowLimousine', host='localhost', port=5432)
cur=conn.cursor(cursor_factory=RealDictCursor)
for tid in (97112,100042):
    cur.execute("SELECT transaction_id, account_number, transaction_date, debit_amount, description, receipt_id, source_file, import_batch FROM banking_transactions WHERE transaction_id=%s", (tid,))
    print('\nBT', dict(cur.fetchone()))
    cur.execute("SELECT receipt_id, vendor_name, gross_amount, receipt_date, banking_transaction_id, receipt_source, exclude_from_reports FROM receipts WHERE banking_transaction_id=%s ORDER BY receipt_id", (tid,))
    rs=cur.fetchall(); print('receipts linked via receipts:', len(rs));
    for r in rs: print(dict(r))
    cur.execute("SELECT * FROM receipt_banking_links WHERE transaction_id=%s ORDER BY receipt_id LIMIT 20", (tid,))
    ls=cur.fetchall(); print('receipt_banking_links rows:', len(ls));
    for l in ls: print(dict(l))
cur.close(); conn.close()
