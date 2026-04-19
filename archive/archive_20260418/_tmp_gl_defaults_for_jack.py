import psycopg2
from psycopg2.extras import RealDictCursor
conn = psycopg2.connect(host='localhost',port=5432,dbname='almsdata',user='postgres',password='ArrowLimousine')
cur = conn.cursor(cursor_factory=RealDictCursor)
cur.execute('''
SELECT COALESCE(gl_account_code, gl_code) AS gl, COUNT(*) AS cnt,
       ROUND(AVG(COALESCE(gst_amount,0))::numeric,2) AS avg_gst
FROM receipts
WHERE receipt_date BETWEEN DATE '2013-01-01' AND DATE '2013-12-31'
  AND (COALESCE(vendor_name,'') ~* '(LEASE|JACK CARTER|FINANCE)' OR COALESCE(description,'') ~* '(LEASE|JACK CARTER|FINANCE)')
GROUP BY COALESCE(gl_account_code, gl_code)
ORDER BY cnt DESC
''')
print('gl usage:')
for r in cur.fetchall():
    print(r['gl'], r['cnt'], r['avg_gst'])

cur.execute('''
SELECT receipt_id, receipt_date, vendor_name, description, gross_amount, gst_amount, COALESCE(gl_account_code, gl_code) AS gl
FROM receipts
WHERE receipt_date BETWEEN DATE '2013-01-01' AND DATE '2013-12-31'
  AND (COALESCE(vendor_name,'') ~* 'JACK CARTER' OR COALESCE(description,'') ~* 'JACK CARTER')
ORDER BY receipt_date, receipt_id
''')
print('\njack carter existing rows:')
for r in cur.fetchall():
    print(r['receipt_id'], r['receipt_date'], r['vendor_name'], r['gross_amount'], r['gst_amount'], r['gl'], r['description'])

cur.close(); conn.close()
