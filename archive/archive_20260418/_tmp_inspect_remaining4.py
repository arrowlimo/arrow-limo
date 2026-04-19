import psycopg2
from psycopg2.extras import RealDictCursor
conn=psycopg2.connect(dbname='almsdata', user='postgres', password='ArrowLimousine', host='localhost', port=5432)
cur=conn.cursor(cursor_factory=RealDictCursor)
for tid in (97153,102357,102362,97176,82438,95057):
    cur.execute("SELECT transaction_id, account_number, transaction_date, debit_amount, description, source_file, import_batch, receipt_id FROM banking_transactions WHERE transaction_id=%s", (tid,))
    r=cur.fetchone(); print('\nBT', dict(r) if r else None)
    if r:
        cur.execute("SELECT receipt_id, vendor_name, gross_amount, receipt_date, receipt_source, exclude_from_reports, banking_transaction_id FROM receipts WHERE banking_transaction_id=%s ORDER BY receipt_id", (tid,))
        rs=cur.fetchall(); print('receipts', len(rs));
        for x in rs: print(dict(x))
cur.close(); conn.close()
