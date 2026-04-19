import psycopg2
from psycopg2.extras import RealDictCursor

targets = [
    (77875, '2013-02-15', 1885.65, 'AUTO LEASE L08136 JACK CARTER'),
    (60621, '2013-06-06', 101.14, 'Lease Finance Group'),
    (102454, '2013-07-24', 1415.89, 'LEASE FINANCE GR'),
    (102455, '2013-07-24', 707.98, 'LEASE FINANCE GR'),
    (78789, '2013-08-15', 1885.65, 'Rent/Lease JACK CARTER'),
]

conn = psycopg2.connect(host='localhost',port=5432,dbname='almsdata',user='postgres',password='ArrowLimousine')
cur = conn.cursor(cursor_factory=RealDictCursor)

for txn_id, dt, amt, desc in targets:
    print('\n=== TARGET', txn_id, dt, amt, desc)
    cur.execute('''
        SELECT receipt_id, receipt_date, vendor_name, description, gross_amount, banking_transaction_id, gl_account_code, gl_code
        FROM receipts
        WHERE ABS(COALESCE(gross_amount,0) - %s) < 0.005
          AND receipt_date BETWEEN (%s::date - INTERVAL '14 days') AND (%s::date + INTERVAL '14 days')
          AND (
            COALESCE(vendor_name,'') ~* '(LEASE|JACK CARTER|FINANCE|HEFFNER|LFG|FORD CREDIT|RENT)'
            OR COALESCE(description,'') ~* '(LEASE|JACK CARTER|FINANCE|HEFFNER|LFG|FORD CREDIT|RENT)'
          )
        ORDER BY receipt_date, receipt_id
    ''', (amt, dt, dt))
    rows = cur.fetchall()
    print('matches', len(rows))
    for r in rows:
        print(r['receipt_id'], r['receipt_date'], float(r['gross_amount']), r['vendor_name'], '|', r['description'], '| bt', r['banking_transaction_id'])

cur.close(); conn.close()
