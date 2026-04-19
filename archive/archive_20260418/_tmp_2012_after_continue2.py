import psycopg2
from psycopg2.extras import RealDictCursor
conn=psycopg2.connect(dbname='almsdata', user='postgres', password='ArrowLimousine', host='localhost', port=5432)
cur=conn.cursor(cursor_factory=RealDictCursor)

cur.execute("""
SELECT COUNT(*) AS cnt, COALESCE(SUM(gross_amount),0) AS amt
FROM receipts
WHERE EXTRACT(YEAR FROM receipt_date)=2012
  AND COALESCE(gl_account_code,'')=''
""")
print('2012_receipts_missing_gl:', dict(cur.fetchone()))

cur.execute("""
SELECT COUNT(*) AS rows_no_receipt, COALESCE(SUM(debit_amount),0) AS amt_no_receipt
FROM banking_transactions
WHERE EXTRACT(YEAR FROM transaction_date)=2012
  AND COALESCE(debit_amount,0)>0
  AND receipt_id IS NULL
""")
print('2012_unlinked_debits:', dict(cur.fetchone()))

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
LIMIT 15
""")
print('2012_remaining_top_vendors:', cur.fetchall())

cur.close(); conn.close()
