import psycopg2
from psycopg2.extras import RealDictCursor

conn = psycopg2.connect(host='localhost', port=5432, dbname='almsdata', user='postgres', password='ArrowLimousine')
cur = conn.cursor(cursor_factory=RealDictCursor)

cur.execute('''
SELECT receipt_id, receipt_date, vendor_name, description, banking_transaction_id
FROM receipts
WHERE receipt_review_status = 'NON_EXPENSE_REV'
ORDER BY receipt_date, receipt_id
''')
rows = cur.fetchall()
print('non_expense_rev_receipts', len(rows))
linked = [r for r in rows if r['banking_transaction_id'] is not None]
print('with_banking_link', len(linked))
for r in linked:
    print(r['receipt_id'], r['banking_transaction_id'], r['receipt_date'], r['vendor_name'])

cur.close(); conn.close()
