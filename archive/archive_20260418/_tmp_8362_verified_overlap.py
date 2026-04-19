import psycopg2
conn = psycopg2.connect(host='localhost', port=5432, dbname='almsdata', user='postgres', password='ArrowLimousine')
cur = conn.cursor()

# Receipts table columns
cur.execute("""
  SELECT column_name, data_type
  FROM information_schema.columns
  WHERE table_name='receipts'
  ORDER BY ordinal_position
""")
print('=== receipts columns ===')
for r in cur.fetchall():
    print(f'  {r[0]:<40} {r[1]}')

# How many verified 8362 rows (2012-2014, with receipt links) match a 1615 row?
cur.execute("""
  SELECT COUNT(DISTINCT bt8.transaction_id)
  FROM banking_transactions bt8
  JOIN banking_transactions bt1
    ON bt1.account_number='1615'
    AND bt1.transaction_date = bt8.transaction_date
    AND COALESCE(bt1.debit_amount,0) = COALESCE(bt8.debit_amount,0)
    AND COALESCE(bt1.credit_amount,0) = COALESCE(bt8.credit_amount,0)
  WHERE bt8.account_number='0228362'
  AND bt8.transaction_date BETWEEN '2012-01-01' AND '2014-12-31'
  AND bt8.verified=TRUE
  AND EXISTS (SELECT 1 FROM receipt_banking_links rbl WHERE rbl.transaction_id=bt8.transaction_id)
""")
print(f'\nVerified 8362 rows that match 1615 by (date,debit,credit): {cur.fetchone()[0]}')

# Preview a few - show both 8362 fields and linked receipt fields
cur.execute("""
  SELECT
    bt8.transaction_id   AS bt8_id,
    bt1.transaction_id   AS bt1_id,
    bt8.transaction_date,
    bt8.debit_amount,
    bt8.credit_amount,
    bt8.description      AS desc_8362,
    bt1.description      AS desc_1615,
    bt8.category         AS cat_8362,
    bt1.category         AS cat_1615,
    bt8.vendor_extracted AS vendor_8362,
    bt1.vendor_extracted AS vendor_1615,
    bt8.reconciliation_status   AS status_8362,
    bt1.reconciliation_status   AS status_1615,
    bt8.reconciled_receipt_id   AS rec_rcpt_8362,
    bt1.reconciled_receipt_id   AS rec_rcpt_1615,
    bt8.is_transfer      AS xfer_8362,
    bt1.is_transfer      AS xfer_1615,
    bt8.reconciliation_notes    AS notes_8362,
    r8.description       AS receipt_desc,
    r8.gross_amount      AS receipt_amt,
    r8.vendor_name       AS receipt_vendor,
    r8.canonical_vendor  AS receipt_canonical
  FROM banking_transactions bt8
  JOIN banking_transactions bt1
    ON bt1.account_number='1615'
    AND bt1.transaction_date = bt8.transaction_date
    AND COALESCE(bt1.debit_amount,0) = COALESCE(bt8.debit_amount,0)
    AND COALESCE(bt1.credit_amount,0) = COALESCE(bt8.credit_amount,0)
  JOIN receipt_banking_links rbl ON rbl.transaction_id = bt8.transaction_id
  JOIN receipts r8 ON r8.receipt_id = rbl.receipt_id
  WHERE bt8.account_number='0228362'
  AND bt8.transaction_date BETWEEN '2012-01-01' AND '2014-12-31'
  AND bt8.verified=TRUE
  LIMIT 6
""")
print('\n=== Sample verified 8362 <-> 1615 match pairs ===')
cols = [d[0] for d in cur.description]
for row in cur.fetchall():
    for c, v in zip(cols, row):
        print(f'  {c}: {v}')
    print()

conn.close()
