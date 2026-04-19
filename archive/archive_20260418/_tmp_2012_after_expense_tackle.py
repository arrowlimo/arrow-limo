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
WITH p AS (
  SELECT charter_id::text AS charter_id, COALESCE(SUM(amount),0) AS paid_total
  FROM charter_payments
  GROUP BY charter_id::text
)
SELECT COALESCE(SUM(c.grand_total),0)-COALESCE(SUM(p.paid_total),0) AS gap
FROM charters c
LEFT JOIN p ON p.charter_id = c.reserve_number::text
WHERE EXTRACT(YEAR FROM c.charter_date)=2012
  AND COALESCE(c.grand_total,0)>0
""")
print('2012_charter_gap:', dict(cur.fetchone()))

cur.close(); conn.close()
