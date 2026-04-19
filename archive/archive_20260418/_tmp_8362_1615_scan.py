import psycopg2
from psycopg2.extras import RealDictCursor

conn=psycopg2.connect(dbname='almsdata', user='postgres', password='ArrowLimousine', host='localhost', port=5432)
cur=conn.cursor(cursor_factory=RealDictCursor)

# Check the two transaction IDs visible in UI
cur.execute("""
SELECT transaction_id, account_number, transaction_date, debit_amount, credit_amount, vendor_extracted, description, source_file
FROM banking_transactions
WHERE transaction_id IN (100042, 97112)
ORDER BY transaction_id
""")
print('UI_IDS:')
for r in cur.fetchall():
    print(dict(r))

# Exact same date+amount+normalized vendor across 8362 and 1615
cur.execute("""
WITH bt AS (
  SELECT transaction_id, account_number, transaction_date,
         COALESCE(debit_amount,0) AS debit_amount,
         COALESCE(credit_amount,0) AS credit_amount,
         UPPER(TRIM(COALESCE(NULLIF(vendor_extracted,''), NULLIF(description,''), ''))) AS norm_vendor,
         description,
         source_file
  FROM banking_transactions
  WHERE account_number IN ('0228362','8362','1615')
), x AS (
  SELECT a.transaction_id AS tx_8362, b.transaction_id AS tx_1615,
         a.transaction_date AS d_8362, b.transaction_date AS d_1615,
         a.debit_amount AS amt_8362, b.debit_amount AS amt_1615,
         a.norm_vendor AS vendor_8362, b.norm_vendor AS vendor_1615,
         a.source_file AS sf_8362, b.source_file AS sf_1615,
         ABS(a.transaction_date - b.transaction_date) AS day_diff
  FROM bt a
  JOIN bt b
    ON a.account_number IN ('0228362','8362')
   AND b.account_number = '1615'
   AND ABS(a.debit_amount - b.debit_amount) < 0.01
   AND a.debit_amount > 0
   AND b.debit_amount > 0
   AND ABS(a.transaction_date - b.transaction_date) <= 3
   AND a.norm_vendor <> ''
   AND b.norm_vendor <> ''
   AND (
      a.norm_vendor = b.norm_vendor
      OR a.norm_vendor LIKE '%' || b.norm_vendor || '%'
      OR b.norm_vendor LIKE '%' || a.norm_vendor || '%'
   )
)
SELECT COUNT(*) AS candidate_pairs
FROM x
""")
print('candidate_pairs_3day_vendor_amt:', cur.fetchone()['candidate_pairs'])

# potential contaminated 8362 rows with explicit 1615 source tags
cur.execute("""
SELECT COUNT(*) AS cnt
FROM banking_transactions
WHERE account_number IN ('0228362','8362')
  AND (
    COALESCE(source_file,'') ILIKE '%1615%'
    OR COALESCE(description,'') ILIKE '%1615%'
  )
""")
print('rows_8362_with_1615_signals:', cur.fetchone()['cnt'])

cur.close(); conn.close()
