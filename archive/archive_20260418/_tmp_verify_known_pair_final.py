import psycopg2
from psycopg2.extras import RealDictCursor
conn=psycopg2.connect(dbname='almsdata', user='postgres', password='ArrowLimousine', host='localhost', port=5432)
cur=conn.cursor(cursor_factory=RealDictCursor)
cur.execute("SELECT COUNT(*) AS c FROM banking_transactions WHERE transaction_id=97112")
print('tx97112_exists', cur.fetchone()['c'])
cur.execute("SELECT transaction_id, account_number, transaction_date, debit_amount, description, receipt_id FROM banking_transactions WHERE transaction_id=100042")
print('tx100042', dict(cur.fetchone()))
cur.execute("SELECT receipt_id, vendor_name, gross_amount, receipt_date, banking_transaction_id, exclude_from_reports FROM receipts WHERE banking_transaction_id=100042 ORDER BY receipt_id")
for r in cur.fetchall():
    print(dict(r))
cur.close(); conn.close()
