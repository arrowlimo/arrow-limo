import psycopg2
from psycopg2.extras import RealDictCursor
conn = psycopg2.connect(host='localhost',port=5432,dbname='almsdata',user='postgres',password='ArrowLimousine')
cur = conn.cursor(cursor_factory=RealDictCursor)

ids = [77875,60621,102454,102455,78789]
cur.execute('''
SELECT bt.transaction_id, bt.transaction_date, bt.description, bt.debit_amount,
       r.receipt_id, r.vendor_name, r.gross_amount, r.gst_amount, r.gl_account_code, r.receipt_source
FROM banking_transactions bt
LEFT JOIN receipts r ON r.banking_transaction_id = bt.transaction_id
WHERE bt.transaction_id = ANY(%s)
ORDER BY bt.transaction_id, r.receipt_id
''', (ids,))
rows = cur.fetchall()
print('linked_rows', len(rows))
for r in rows:
    print(r['transaction_id'], r['receipt_id'], r['vendor_name'], float(r['gross_amount']) if r['gross_amount'] is not None else None, float(r['gst_amount']) if r['gst_amount'] is not None else None, r['gl_account_code'], r['receipt_source'])

cur.execute('SELECT COUNT(*) FROM backup_easyfix_lease_links_20260407')
print('backup_easyfix_lease_links_rows', cur.fetchone()['count'])

cur.close(); conn.close()
