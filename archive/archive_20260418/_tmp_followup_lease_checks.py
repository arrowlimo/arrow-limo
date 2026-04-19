import psycopg2
from psycopg2.extras import RealDictCursor
conn = psycopg2.connect(host='localhost',port=5432,dbname='almsdata',user='postgres',password='ArrowLimousine')
cur = conn.cursor(cursor_factory=RealDictCursor)
lease_regex = r'(LEASE|FORD\\s*CREDIT|TOYOTA\\s*CREDIT|GM\\s*FINANCIAL|MERCEDES|HONDA\\s*FINANCE|VEHICLE\\s*LEASE|AUTO\\s*LEASE|LOAN\\s*PAYMENT)'
cur.execute('''
WITH lease_banking AS (
  SELECT bt.transaction_id, bt.transaction_date, bt.description, COALESCE(bt.debit_amount,0) AS debit_amount, bt.account_number
  FROM banking_transactions bt
  WHERE bt.transaction_date >= DATE '2012-01-01' AND bt.transaction_date < DATE '2015-01-01'
    AND COALESCE(bt.debit_amount,0) > 0
    AND COALESCE(bt.description,'') ~* %s
)
SELECT lb.*
FROM lease_banking lb
LEFT JOIN receipts r ON r.banking_transaction_id = lb.transaction_id
WHERE r.receipt_id IS NULL
ORDER BY lb.transaction_date, lb.transaction_id
''', (lease_regex,))
rows = cur.fetchall()
print('MISSING_LINK_COUNT', len(rows))
for r in rows[:20]:
  print(r['transaction_id'], r['transaction_date'], r['account_number'], float(r['debit_amount']), r['description'])

cur.execute('''
WITH lease_receipts AS (
  SELECT receipt_id, receipt_date, vendor_name, gross_amount, gst_amount, gst_exempt, description
  FROM receipts
  WHERE receipt_date >= DATE '2012-01-01' AND receipt_date < DATE '2015-01-01'
    AND (
      COALESCE(vendor_name,'') ~* %s OR COALESCE(canonical_vendor,'') ~* %s OR COALESCE(description,'') ~* %s OR COALESCE(category,'') ~* %s OR COALESCE(expense::text,'') ~* %s
    )
)
SELECT *
FROM lease_receipts
WHERE COALESCE(gst_exempt,false)=false AND COALESCE(gross_amount,0)>0 AND COALESCE(gst_amount,0)=0
ORDER BY receipt_date, receipt_id
LIMIT 25
''', (lease_regex, lease_regex, lease_regex, lease_regex, lease_regex))
rows = cur.fetchall()
print('LEASE_MISSING_GST_SAMPLE', len(rows))
for r in rows:
  print(r['receipt_id'], r['receipt_date'], float(r['gross_amount']), r['vendor_name'], r['description'])
cur.close(); conn.close()
