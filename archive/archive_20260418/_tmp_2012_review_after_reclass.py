import psycopg2
from psycopg2.extras import RealDictCursor
conn=psycopg2.connect(dbname='almsdata', user='postgres', password='ArrowLimousine', host='localhost', port=5432)
cur=conn.cursor(cursor_factory=RealDictCursor)

cur.execute("""
SELECT COUNT(*) AS cnt, COALESCE(SUM(gross_amount),0) AS amt
FROM receipts
WHERE EXTRACT(YEAR FROM receipt_date)=2012
  AND receipt_source='auto_2012_unlinked_debit_review_backfill'
  AND COALESCE(exclude_from_reports,false)=true
""")
print('2012_review_still_excluded:', dict(cur.fetchone()))

cur.execute("""
SELECT gl_account_code, COUNT(*) cnt, COALESCE(SUM(gross_amount),0) amt
FROM receipts
WHERE EXTRACT(YEAR FROM receipt_date)=2012
  AND receipt_source='auto_2012_unlinked_debit_review_backfill'
GROUP BY gl_account_code
ORDER BY amt DESC
""")
print('2012_review_gl_distribution:', cur.fetchall())

cur.close(); conn.close()
