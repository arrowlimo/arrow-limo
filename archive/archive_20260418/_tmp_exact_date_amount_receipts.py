import psycopg2
from psycopg2.extras import RealDictCursor
conn = psycopg2.connect(host='localhost',port=5432,dbname='almsdata',user='postgres',password='ArrowLimousine')
cur = conn.cursor(cursor_factory=RealDictCursor)

checks = [
 ('2013-06-06', 101.14),
 ('2013-07-24', 1415.89),
 ('2013-07-24', 707.98),
 ('2013-02-15', 1885.65),
 ('2013-08-15', 1885.65),
]
for dt, amt in checks:
    print('\n--', dt, amt)
    cur.execute('''
    SELECT receipt_id, receipt_date, vendor_name, description, gross_amount, banking_transaction_id, receipt_source, gl_account_code, gl_code
    FROM receipts
    WHERE receipt_date = %s AND ABS(COALESCE(gross_amount,0) - %s) < 0.005
    ORDER BY receipt_id
    ''', (dt, amt))
    rows = cur.fetchall()
    print('rows', len(rows))
    for r in rows:
        print(r['receipt_id'], r['vendor_name'], '|', r['description'], '| bt', r['banking_transaction_id'], '| src', r['receipt_source'])

cur.close(); conn.close()
