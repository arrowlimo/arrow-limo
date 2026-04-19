import psycopg2
from psycopg2.extras import RealDictCursor

conn=psycopg2.connect(dbname='almsdata', user='postgres', password='ArrowLimousine', host='localhost', port=5432)
cur=conn.cursor(cursor_factory=RealDictCursor)

y=2012

print('=== 2012 CHARTER INVOICED VS PAID ===')
cur.execute("""
WITH p AS (
  SELECT charter_id::text AS charter_id, COALESCE(SUM(amount),0) AS paid_total
  FROM charter_payments
  GROUP BY charter_id::text
)
SELECT COUNT(*) AS charter_count,
       COALESCE(SUM(c.grand_total),0) AS invoiced,
       COALESCE(SUM(p.paid_total),0) AS paid,
       COALESCE(SUM(c.grand_total),0)-COALESCE(SUM(p.paid_total),0) AS gap
FROM charters c
LEFT JOIN p ON p.charter_id = c.reserve_number::text
WHERE EXTRACT(YEAR FROM c.charter_date)=%s
  AND COALESCE(c.grand_total,0) > 0
""", (y,))
print(dict(cur.fetchone()))

print('\n=== 2012 CHARTER_PAYMENTS UNLINKED ===')
cur.execute("""
SELECT COUNT(*) AS cnt, COALESCE(SUM(amount),0) AS amt
FROM charter_payments
WHERE EXTRACT(YEAR FROM payment_date)=%s
  AND charter_id IS NULL
""", (y,))
print(dict(cur.fetchone()))

print('\n=== 2012 BANKING DEBITS WITHOUT RECEIPT LINK ===')
cur.execute("""
SELECT COUNT(*) AS rows_no_receipt, COALESCE(SUM(debit_amount),0) AS amt_no_receipt
FROM banking_transactions
WHERE EXTRACT(YEAR FROM transaction_date)=%s
  AND COALESCE(debit_amount,0)>0
  AND receipt_id IS NULL
""", (y,))
print(dict(cur.fetchone()))

print('\n=== 2012 RECEIPTS WITHOUT GL CODE ===')
cur.execute("""
SELECT COUNT(*) AS cnt, COALESCE(SUM(gross_amount),0) AS amt
FROM receipts
WHERE EXTRACT(YEAR FROM receipt_date)=%s
  AND COALESCE(gl_account_code,'')=''
""", (y,))
print(dict(cur.fetchone()))

print('\n=== 2012 LEASE-LIKE ZERO GST REMAINING ===')
cur.execute("""
SELECT COUNT(*) AS cnt, COALESCE(SUM(gross_amount),0) AS amt
FROM receipts
WHERE EXTRACT(YEAR FROM receipt_date)=%s
  AND COALESCE(gross_amount,0)>0
  AND (
        COALESCE(category,'') ILIKE '%lease%'
     OR COALESCE(description,'') ILIKE '%lease%'
     OR COALESCE(vendor_name,'') ILIKE '%lease%'
      )
  AND COALESCE(gst_amount,0)=0
""", (y,))
print(dict(cur.fetchone()))

cur.close(); conn.close()
