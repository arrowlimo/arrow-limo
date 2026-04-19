import psycopg2
conn = psycopg2.connect(host='localhost', port=5432, dbname='almsdata', user='postgres', password='ArrowLimousine')
cur = conn.cursor()

cur.execute("""
  SELECT column_name, data_type
  FROM information_schema.columns
  WHERE table_name='banking_transactions'
  ORDER BY ordinal_position
""")
print('=== banking_transactions columns ===')
for r in cur.fetchall():
    print(f'  {r[0]:<40} {r[1]}')

cur.execute("""
  SELECT column_name, data_type
  FROM information_schema.columns
  WHERE table_name='receipt_banking_links'
  ORDER BY ordinal_position
""")
print()
print('=== receipt_banking_links columns ===')
for r in cur.fetchall():
    print(f'  {r[0]:<40} {r[1]}')

# Count verified=True 8362 rows in 2012-2014 with receipt links
cur.execute("""
  SELECT COUNT(*)
  FROM banking_transactions bt
  WHERE bt.account_number='0228362'
  AND bt.transaction_date BETWEEN '2012-01-01' AND '2014-12-31'
  AND bt.verified=TRUE
  AND EXISTS (SELECT 1 FROM receipt_banking_links rbl WHERE rbl.transaction_id=bt.transaction_id)
""")
print(f'\n8362 verified=TRUE with receipt links (2012-2014): count={cur.fetchone()[0]}')

# What fields differ: look at a sample pair 8362 vs 1615 same date/amount
cur.execute("""
  SELECT bt.*
  FROM banking_transactions bt
  WHERE bt.account_number='0228362'
  AND bt.transaction_date BETWEEN '2012-01-01' AND '2014-12-31'
  AND bt.verified=TRUE
  AND EXISTS (SELECT 1 FROM receipt_banking_links rbl WHERE rbl.transaction_id=bt.transaction_id)
  LIMIT 3
""")
cols = [d[0] for d in cur.description]
print('\n=== Sample verified 8362 rows with receipts ===')
for row in cur.fetchall():
    for c, v in zip(cols, row):
        if v is not None:
            print(f'  {c}: {v}')
    print()

conn.close()
