import psycopg2
from psycopg2.extras import RealDictCursor

conn = psycopg2.connect(dbname='almsdata', user='postgres', password='ArrowLimousine', host='localhost', port=5432)
cur = conn.cursor(cursor_factory=RealDictCursor)

cur.execute("""
SELECT column_name FROM information_schema.columns
WHERE table_schema='public' AND table_name='receipts'
""")
rcols = {r['column_name'] for r in cur.fetchall()}

has_needs_review = 'needs_review' in rcols
needs_review_expr = 'COALESCE(SUM(CASE WHEN needs_review THEN gross_amount ELSE 0 END),0)' if has_needs_review else '0'

print('=== T2 EXPENSE COVERAGE GAPS ===')
cur.execute(f"""
    SELECT EXTRACT(YEAR FROM receipt_date)::int AS yr,
           COUNT(*) AS receipt_count,
           COALESCE(SUM(gross_amount),0) AS gross,
           COALESCE(SUM(CASE WHEN gl_account_code IS NULL OR gl_account_code='' THEN gross_amount ELSE 0 END),0) AS gross_missing_gl,
           {needs_review_expr} AS gross_needs_review
    FROM receipts
    GROUP BY EXTRACT(YEAR FROM receipt_date)
    ORDER BY yr DESC
""")
for r in cur.fetchall()[:15]:
    print(dict(r))

print('\n=== GST ON LEASE-LIKE RECEIPTS ===')
cur.execute("""
    SELECT COUNT(*) AS cnt, COALESCE(SUM(gross_amount),0) AS amt
    FROM receipts
    WHERE gross_amount > 0
      AND (
            COALESCE(category,'') ILIKE '%lease%'
         OR COALESCE(description,'') ILIKE '%lease%'
         OR COALESCE(vendor_name,'') ILIKE '%lease%'
          )
""")
print('lease-like receipts total:', dict(cur.fetchone()))

cur.execute("""
    SELECT COUNT(*) AS cnt, COALESCE(SUM(gross_amount),0) AS amt
    FROM receipts
    WHERE gross_amount > 0
      AND (
            COALESCE(category,'') ILIKE '%lease%'
         OR COALESCE(description,'') ILIKE '%lease%'
         OR COALESCE(vendor_name,'') ILIKE '%lease%'
          )
      AND COALESCE(gst_amount,0) = 0
""")
print('lease-like receipts with ZERO gst_amount:', dict(cur.fetchone()))

cur.execute("""
    SELECT EXTRACT(YEAR FROM receipt_date)::int AS yr,
           COUNT(*) AS cnt,
           COALESCE(SUM(gross_amount),0) AS amt
    FROM receipts
    WHERE gross_amount > 0
      AND (
            COALESCE(category,'') ILIKE '%lease%'
         OR COALESCE(description,'') ILIKE '%lease%'
         OR COALESCE(vendor_name,'') ILIKE '%lease%'
          )
      AND COALESCE(gst_amount,0) = 0
    GROUP BY EXTRACT(YEAR FROM receipt_date)
    ORDER BY yr DESC
""")
print('lease-like zero GST by year:', cur.fetchall())

print('\n=== BANK FEES / CHARGES HANDLING ===')
bankfee_pred = """
    (bt.description ILIKE '%SERVICE CHARGE%'
        OR bt.description ILIKE '%BANK FEE%'
        OR bt.description ILIKE '%OVERDRAFT%'
        OR bt.description ILIKE '%NSF FEE%'
        OR bt.description ILIKE '%ACCOUNT FEE%'
        OR bt.description ILIKE '%MONTHLY FEE%'
        OR bt.description ILIKE '%INTERAC FEE%'
        OR COALESCE(bt.vendor_extracted,'') ILIKE '%BANK FEE%'
        OR COALESCE(bt.vendor_extracted,'') ILIKE '%SERVICE CHARGE%')
"""
cur.execute(f"""
    SELECT COUNT(*) AS cnt, COALESCE(SUM(COALESCE(debit_amount,0)),0) AS amt
    FROM banking_transactions bt
    WHERE {bankfee_pred}
      AND COALESCE(bt.debit_amount,0) > 0
""")
print('bank-fee-like banking tx total:', dict(cur.fetchone()))

cur.execute(f"""
    SELECT COUNT(*) AS cnt, COALESCE(SUM(COALESCE(bt.debit_amount,0)),0) AS amt
    FROM banking_transactions bt
    WHERE {bankfee_pred}
      AND COALESCE(bt.debit_amount,0) > 0
      AND bt.receipt_id IS NULL
""")
print('bank-fee-like tx missing receipt link:', dict(cur.fetchone()))

cur.execute("""
    SELECT COALESCE(r.gl_account_code,'') AS gl, COUNT(*) cnt, COALESCE(SUM(r.gross_amount),0) amt
    FROM receipts r
    WHERE (COALESCE(r.category,'') ILIKE '%bank fee%'
        OR COALESCE(r.category,'') ILIKE '%bank charge%'
        OR COALESCE(r.gl_account_code,'')='5900')
    GROUP BY COALESCE(r.gl_account_code,'')
    ORDER BY amt DESC
""")
print('bank-fee-like receipts by GL:', cur.fetchall())

print('\n=== CHARTER INVOICING VS PAYMENTS ===')
cur.execute("""
    WITH p AS (
      SELECT charter_id::text AS charter_id, COALESCE(SUM(amount),0) AS paid_total
      FROM charter_payments
      GROUP BY charter_id::text
    )
    SELECT COUNT(*) AS charter_count,
           COALESCE(SUM(c.grand_total),0) AS invoiced_grand_total,
           COALESCE(SUM(c.total_amount_due),0) AS invoiced_total_amount_due,
           COALESCE(SUM(p.paid_total),0) AS paid_linked,
           COALESCE(SUM(c.grand_total),0) - COALESCE(SUM(p.paid_total),0) AS ar_gap_grand
    FROM charters c
    LEFT JOIN p ON p.charter_id = c.reserve_number::text
    WHERE COALESCE(c.grand_total,0) > 0
""")
print(dict(cur.fetchone()))

cur.execute("""
    SELECT COUNT(*) AS cnt, COALESCE(SUM(amount),0) AS amt
    FROM charter_payments
    WHERE charter_id IS NULL
""")
print('charter_payments unlinked (charter_id null):', dict(cur.fetchone()))

cur.execute("""
    SELECT COUNT(*) AS cnt, COALESCE(SUM(amount),0) AS amt
    FROM charter_payments
    WHERE charter_id IS NOT NULL
      AND NOT EXISTS (
        SELECT 1 FROM charters c WHERE c.reserve_number::text = charter_payments.charter_id::text
      )
""")
print('charter_payments linked to missing reserve_number:', dict(cur.fetchone()))

print('\n=== BANKING CREDITS (REVENUE-RISK CHECK) ===')
cur.execute("""
    SELECT EXTRACT(YEAR FROM transaction_date)::int AS yr,
           COUNT(*) AS credit_rows,
           COALESCE(SUM(credit_amount),0) AS credit_amt,
           COALESCE(SUM(CASE WHEN receipt_id IS NULL THEN credit_amount ELSE 0 END),0) AS unlinked_credit_amt
    FROM banking_transactions
    WHERE COALESCE(credit_amount,0) > 0
    GROUP BY EXTRACT(YEAR FROM transaction_date)
    ORDER BY yr DESC
""")
for r in cur.fetchall()[:15]:
    print(dict(r))

print('\n=== DEBIT TX WITHOUT RECEIPTS ===')
cur.execute("""
    SELECT EXTRACT(YEAR FROM transaction_date)::int AS yr,
           COUNT(*) AS debit_rows,
           COALESCE(SUM(debit_amount),0) AS debit_amt,
           COALESCE(SUM(CASE WHEN receipt_id IS NULL THEN debit_amount ELSE 0 END),0) AS debit_amt_no_receipt,
           COUNT(CASE WHEN receipt_id IS NULL THEN 1 END) AS rows_no_receipt
    FROM banking_transactions
    WHERE COALESCE(debit_amount,0) > 0
    GROUP BY EXTRACT(YEAR FROM transaction_date)
    ORDER BY yr DESC
""")
for r in cur.fetchall()[:15]:
    print(dict(r))

cur.close()
conn.close()
