import psycopg2
from psycopg2.extras import RealDictCursor

conn=psycopg2.connect(dbname='almsdata', user='postgres', password='ArrowLimousine', host='localhost', port=5432)
cur=conn.cursor(cursor_factory=RealDictCursor)

print('=== 409 REVIEW BACKFILL: SUMMARY ===')
cur.execute("""
SELECT COUNT(*) AS cnt, COALESCE(SUM(gross_amount),0) AS amt
FROM receipts
WHERE EXTRACT(YEAR FROM receipt_date)=2012
  AND receipt_source='auto_2012_unlinked_debit_review_backfill'
  AND COALESCE(exclude_from_reports,false)=true
""")
print(dict(cur.fetchone()))

print('\n=== BY VENDOR NAME ===')
cur.execute("""
SELECT COALESCE(vendor_name,'(blank)') AS vendor,
       COUNT(*) AS cnt,
       COALESCE(SUM(gross_amount),0) AS amt
FROM receipts
WHERE EXTRACT(YEAR FROM receipt_date)=2012
  AND receipt_source='auto_2012_unlinked_debit_review_backfill'
GROUP BY COALESCE(vendor_name,'(blank)')
ORDER BY amt DESC, cnt DESC
LIMIT 30
""")
for r in cur.fetchall():
    print(dict(r))

print('\n=== BY DESCRIPTION PATTERN ===')
cur.execute("""
SELECT
  SUM(CASE WHEN COALESCE(description,'') ~* 'CHQ|CHEQUE' THEN 1 ELSE 0 END) AS cheque_rows,
  SUM(CASE WHEN COALESCE(description,'') ~* 'CHQ|CHEQUE' THEN COALESCE(gross_amount,0) ELSE 0 END) AS cheque_amt,
  SUM(CASE WHEN COALESCE(description,'') ~* 'CASH WITHDRAWAL|ATM WITHDRAWAL' THEN 1 ELSE 0 END) AS cash_rows,
  SUM(CASE WHEN COALESCE(description,'') ~* 'CASH WITHDRAWAL|ATM WITHDRAWAL' THEN COALESCE(gross_amount,0) ELSE 0 END) AS cash_amt,
  SUM(CASE WHEN COALESCE(description,'') ~* 'NSF|OVERDRAFT|BANK FEE|SERVICE CHARGE|MERCHANT' THEN 1 ELSE 0 END) AS fee_rows,
  SUM(CASE WHEN COALESCE(description,'') ~* 'NSF|OVERDRAFT|BANK FEE|SERVICE CHARGE|MERCHANT' THEN COALESCE(gross_amount,0) ELSE 0 END) AS fee_amt,
  SUM(CASE WHEN NOT (COALESCE(description,'') ~* 'CHQ|CHEQUE|CASH WITHDRAWAL|ATM WITHDRAWAL|NSF|OVERDRAFT|BANK FEE|SERVICE CHARGE|MERCHANT') THEN 1 ELSE 0 END) AS other_rows,
  SUM(CASE WHEN NOT (COALESCE(description,'') ~* 'CHQ|CHEQUE|CASH WITHDRAWAL|ATM WITHDRAWAL|NSF|OVERDRAFT|BANK FEE|SERVICE CHARGE|MERCHANT') THEN COALESCE(gross_amount,0) ELSE 0 END) AS other_amt
FROM receipts
WHERE EXTRACT(YEAR FROM receipt_date)=2012
  AND receipt_source='auto_2012_unlinked_debit_review_backfill'
""")
print(dict(cur.fetchone()))

print('\n=== TOP 40 INDIVIDUAL ENTRIES ===')
cur.execute("""
SELECT receipt_id, receipt_date, vendor_name, description, gross_amount, gl_account_code, exclude_from_reports
FROM receipts
WHERE EXTRACT(YEAR FROM receipt_date)=2012
  AND receipt_source='auto_2012_unlinked_debit_review_backfill'
ORDER BY gross_amount DESC, receipt_id
LIMIT 40
""")
for r in cur.fetchall():
    print(dict(r))

cur.close(); conn.close()
