import psycopg2
from psycopg2.extras import RealDictCursor

conn=psycopg2.connect(dbname='almsdata', user='postgres', password='ArrowLimousine', host='localhost', port=5432)
cur=conn.cursor(cursor_factory=RealDictCursor)

print('=== 2012 UNLINKED DEBITS TOP VENDORS ===')
cur.execute("""
SELECT COALESCE(vendor_extracted,'(none)') AS vendor,
       COUNT(*) AS cnt,
       COALESCE(SUM(debit_amount),0) AS amt
FROM banking_transactions
WHERE EXTRACT(YEAR FROM transaction_date)=2012
  AND COALESCE(debit_amount,0)>0
  AND receipt_id IS NULL
GROUP BY COALESCE(vendor_extracted,'(none)')
ORDER BY amt DESC
LIMIT 40
""")
for r in cur.fetchall():
    print(dict(r))

print('\n=== 2012 UNLINKED DEBITS SAMPLE (LATEST 80) ===')
cur.execute("""
SELECT transaction_id, transaction_date, debit_amount, vendor_extracted, description
FROM banking_transactions
WHERE EXTRACT(YEAR FROM transaction_date)=2012
  AND COALESCE(debit_amount,0)>0
  AND receipt_id IS NULL
ORDER BY transaction_date DESC, transaction_id DESC
LIMIT 80
""")
for r in cur.fetchall():
    print(dict(r))

print('\n=== 2012 RECEIPTS MISSING GL CODE ===')
cur.execute("""
SELECT receipt_id, receipt_date, vendor_name, description, gross_amount, gst_amount, category, gl_account_code
FROM receipts
WHERE EXTRACT(YEAR FROM receipt_date)=2012
  AND COALESCE(gl_account_code,'')=''
ORDER BY receipt_date, receipt_id
""")
for r in cur.fetchall():
    print(dict(r))

cur.close(); conn.close()
