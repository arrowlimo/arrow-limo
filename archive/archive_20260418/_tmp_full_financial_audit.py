import psycopg2
from psycopg2.extras import RealDictCursor

conn = psycopg2.connect(dbname='almsdata', user='postgres', password='ArrowLimousine', host='localhost', port=5432)
cur = conn.cursor(cursor_factory=RealDictCursor)

print('=== SCHEMA SNAPSHOT ===')
for t in ['receipts','chart_of_accounts','banking_transactions','charters','charter_payments']:
    cur.execute("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema='public' AND table_name=%s
        ORDER BY ordinal_position
    """, (t,))
    cols = [r['column_name'] for r in cur.fetchall()]
    print(f"{t}: {', '.join(cols[:20])}" + (" ..." if len(cols)>20 else ""))

print('\n=== GL CODE DUPLICATION / INTEGRITY ===')
cur.execute("""
    SELECT COUNT(*) total_rows,
           COUNT(DISTINCT account_code) distinct_codes,
           COUNT(DISTINCT account_name) distinct_names
    FROM chart_of_accounts
""")
print(dict(cur.fetchone()))

cur.execute("""
    SELECT account_code, COUNT(*) c
    FROM chart_of_accounts
    GROUP BY account_code
    HAVING COUNT(*) > 1
    ORDER BY c DESC, account_code
""")
dup_codes = cur.fetchall()
print(f"duplicate account_code rows: {len(dup_codes)}")

cur.execute("""
    SELECT account_name, COUNT(*) c
    FROM chart_of_accounts
    GROUP BY account_name
    HAVING COUNT(*) > 1
    ORDER BY c DESC, account_name
    LIMIT 20
""")
print('duplicate account_name sample:', cur.fetchall())

cur.execute("""
    SELECT COUNT(*) AS cnt
    FROM receipts
    WHERE (gl_account_code IS NULL OR gl_account_code='')
""")
print('receipts missing gl_account_code:', cur.fetchone()['cnt'])

cur.execute("""
    SELECT COALESCE(gl_account_code,'') AS gl, COUNT(*) c, COALESCE(SUM(gross_amount),0) amt
    FROM receipts
    GROUP BY COALESCE(gl_account_code,'')
    ORDER BY c DESC
    LIMIT 20
""")
print('top receipt gl_account_code values:', cur.fetchall())

cur.execute("""
    SELECT r.gl_account_code, COUNT(*) c, COALESCE(SUM(r.gross_amount),0) amt
    FROM receipts r
    LEFT JOIN chart_of_accounts coa ON coa.account_code = r.gl_account_code
    WHERE r.gl_account_code IS NOT NULL AND r.gl_account_code <> ''
      AND coa.account_code IS NULL
    GROUP BY r.gl_account_code
    ORDER BY amt DESC
    LIMIT 30
""")
missing_coa = cur.fetchall()
print('receipt GL codes not in chart_of_accounts:', missing_coa)

print('\n=== T2 EXPENSE COVERAGE GAPS ===')
cur.execute("""
    SELECT EXTRACT(YEAR FROM receipt_date)::int AS yr,
           COUNT(*) AS receipt_count,
           COALESCE(SUM(gross_amount),0) AS gross,
           COALESCE(SUM(CASE WHEN gl_account_code IS NULL OR gl_account_code='' THEN gross_amount ELSE 0 END),0) AS gross_missing_gl,
           COALESCE(SUM(CASE WHEN needs_review THEN gross_amount ELSE 0 END),0) AS gross_needs_review
    FROM receipts
    GROUP BY EXTRACT(YEAR FROM receipt_date)
    ORDER BY yr DESC
""")
for r in cur.fetchall()[:10]:
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
    SELECT receipt_id, receipt_date, vendor_name, category, gross_amount, gst_amount, description
    FROM receipts
    WHERE gross_amount > 0
      AND (
            COALESCE(category,'') ILIKE '%lease%'
         OR COALESCE(description,'') ILIKE '%lease%'
         OR COALESCE(vendor_name,'') ILIKE '%lease%'
          )
      AND COALESCE(gst_amount,0) = 0
    ORDER BY receipt_date DESC
    LIMIT 25
""")
print('lease-like zero-gst sample:', cur.fetchall())

print('\n=== BANK FEES / CHARGES HANDLING ===')
cur.execute("""
    SELECT COUNT(*) AS cnt, COALESCE(SUM(COALESCE(debit_amount,0)),0) AS amt
    FROM banking_transactions bt
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
""")
print('bank-fee-like banking tx total:', dict(cur.fetchone()))

cur.execute("""
    SELECT COUNT(*) AS cnt, COALESCE(SUM(COALESCE(bt.debit_amount,0)),0) AS amt
    FROM banking_transactions bt
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
      AND bt.receipt_id IS NULL
""")
print('bank-fee-like tx missing receipt link:', dict(cur.fetchone()))

cur.execute("""
    SELECT COUNT(*) AS cnt, COALESCE(SUM(r.gross_amount),0) AS amt
    FROM receipts r
    WHERE (COALESCE(r.category,'') ILIKE '%bank fee%'
        OR COALESCE(r.category,'') ILIKE '%bank charge%'
        OR COALESCE(r.gl_account_code,'')='5900')
      AND (r.banking_transaction_id IS NULL)
""")
print('bank-fee-coded receipts missing banking link:', dict(cur.fetchone()))

print('\n=== CHARTER INVOICING VS REVENUE/PAYMENTS ===')
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

print('\n=== BANKING USED AS REVENUE RISK ===')
cur.execute("""
    SELECT EXTRACT(YEAR FROM transaction_date)::int AS yr,
           COUNT(*) AS credit_rows,
           COALESCE(SUM(credit_amount),0) AS credit_amt,
           COALESCE(SUM(CASE WHEN receipt_id IS NULL THEN credit_amount ELSE 0 END),0) AS unlinked_credit_amt
    FROM banking_transactions
    WHERE COALESCE(credit_amount,0) > 0
    GROUP BY EXTRACT(YEAR FROM transaction_date)
    ORDER BY yr DESC
    LIMIT 10
""")
for r in cur.fetchall():
    print(dict(r))

print('\n=== MISSING RECEIPTS FOR BANKING TX (EXPENSE SIDE) ===')
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
    LIMIT 10
""")
for r in cur.fetchall():
    print(dict(r))

cur.close()
conn.close()
