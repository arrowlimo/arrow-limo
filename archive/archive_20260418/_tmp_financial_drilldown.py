import psycopg2
from psycopg2.extras import RealDictCursor

conn = psycopg2.connect(dbname='almsdata', user='postgres', password='ArrowLimousine', host='localhost', port=5432)
cur = conn.cursor(cursor_factory=RealDictCursor)

print('=== 1) RECEIPTS MISSING GL ACCOUNT CODE (BY YEAR) ===')
cur.execute("""
SELECT EXTRACT(YEAR FROM receipt_date)::int AS yr,
       COUNT(*) AS cnt,
       COALESCE(SUM(gross_amount),0) AS amt
FROM receipts
WHERE COALESCE(gl_account_code,'')=''
GROUP BY EXTRACT(YEAR FROM receipt_date)
ORDER BY yr DESC
""")
for r in cur.fetchall():
    print(dict(r))

print('\n=== 2) LEASE-LIKE ZERO GST (VENDOR BREAKDOWN) ===')
cur.execute("""
SELECT COALESCE(vendor_name,'(blank)') AS vendor,
       COUNT(*) AS cnt,
       COALESCE(SUM(gross_amount),0) AS amt,
       COALESCE(SUM(CASE WHEN COALESCE(gst_amount,0)>0 THEN 1 ELSE 0 END),0) AS with_gst_rows
FROM receipts
WHERE gross_amount > 0
  AND (
        COALESCE(category,'') ILIKE '%lease%'
     OR COALESCE(description,'') ILIKE '%lease%'
     OR COALESCE(vendor_name,'') ILIKE '%lease%'
      )
  AND COALESCE(gst_amount,0)=0
GROUP BY COALESCE(vendor_name,'(blank)')
ORDER BY amt DESC
LIMIT 50
""")
for r in cur.fetchall():
    print(dict(r))

print('\n=== 3) BANK-FEE-LIKE TX WITH RECEIPT GL NOT 5900 ===')
cur.execute("""
SELECT bt.transaction_id,
       bt.transaction_date,
       bt.description,
       bt.debit_amount,
       r.receipt_id,
       r.vendor_name,
       COALESCE(r.gl_account_code,'') AS gl_account_code,
       COALESCE(r.category,'') AS category,
       COALESCE(r.gross_amount,0) AS receipt_amount
FROM banking_transactions bt
JOIN receipts r ON r.banking_transaction_id = bt.transaction_id
WHERE (bt.description ILIKE '%SERVICE CHARGE%'
    OR bt.description ILIKE '%BANK FEE%'
    OR bt.description ILIKE '%OVERDRAFT%'
    OR bt.description ILIKE '%NSF FEE%'
    OR bt.description ILIKE '%ACCOUNT FEE%'
    OR bt.description ILIKE '%MONTHLY FEE%'
    OR bt.description ILIKE '%INTERAC FEE%'
    OR COALESCE(bt.vendor_extracted,'') ILIKE '%BANK FEE%'
    OR COALESCE(bt.vendor_extracted,'') ILIKE '%SERVICE CHARGE%')
  AND COALESCE(bt.debit_amount,0) > 0
  AND COALESCE(r.gl_account_code,'') <> '5900'
ORDER BY bt.transaction_date DESC
LIMIT 80
""")
rows = cur.fetchall()
print('rows:', len(rows))
for r in rows[:25]:
    print(dict(r))

print('\n=== 4) CHARTER INVOICED VS PAID GAP (BY YEAR) ===')
cur.execute("""
WITH p AS (
    SELECT charter_id::text AS charter_id, COALESCE(SUM(amount),0) AS paid_total
    FROM charter_payments
    GROUP BY charter_id::text
)
SELECT EXTRACT(YEAR FROM c.charter_date)::int AS yr,
       COUNT(*) AS charter_count,
       COALESCE(SUM(c.grand_total),0) AS invoiced,
       COALESCE(SUM(p.paid_total),0) AS paid,
       COALESCE(SUM(c.grand_total),0)-COALESCE(SUM(p.paid_total),0) AS gap
FROM charters c
LEFT JOIN p ON p.charter_id = c.reserve_number::text
WHERE COALESCE(c.grand_total,0) > 0
GROUP BY EXTRACT(YEAR FROM c.charter_date)
ORDER BY yr DESC
""")
for r in cur.fetchall():
    print(dict(r))

print('\n=== 5) CHARTER PAYMENTS UNLINKED SUMMARY BY SOURCE ===')
cur.execute("""
SELECT COALESCE(source,'(null)') AS source,
       COUNT(*) AS cnt,
       COALESCE(SUM(amount),0) AS amt
FROM charter_payments
WHERE charter_id IS NULL
GROUP BY COALESCE(source,'(null)')
ORDER BY amt DESC
""")
for r in cur.fetchall():
    print(dict(r))

print('\n=== 6) DEBIT TX MISSING RECEIPTS (LIKELY EXPENSES, TOP VENDORS) ===')
cur.execute("""
SELECT COALESCE(vendor_extracted,'(none)') AS vendor,
       COUNT(*) AS cnt,
       COALESCE(SUM(debit_amount),0) AS amt
FROM banking_transactions
WHERE COALESCE(debit_amount,0) > 0
  AND receipt_id IS NULL
  AND COALESCE(description,'') !~* '(transfer|e-?transfer|interac\\s*e-?transfer|payment\\s+received|deposit|interest|nsf\\s*reversal|reversal|refund|cheque\\s+deposit|mobile\\s+deposit|from\\s+account|to\\s+account)'
GROUP BY COALESCE(vendor_extracted,'(none)')
ORDER BY amt DESC
LIMIT 50
""")
for r in cur.fetchall():
    print(dict(r))

cur.close()
conn.close()
