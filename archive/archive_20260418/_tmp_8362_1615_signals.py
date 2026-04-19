import psycopg2
from psycopg2.extras import RealDictCursor
conn=psycopg2.connect(dbname='almsdata', user='postgres', password='ArrowLimousine', host='localhost', port=5432)
cur=conn.cursor(cursor_factory=RealDictCursor)
cur.execute("""
SELECT transaction_id, account_number, transaction_date, debit_amount, description, source_file
FROM banking_transactions
WHERE account_number IN ('0228362','8362')
  AND (COALESCE(source_file,'') ILIKE '%1615%' OR COALESCE(description,'') ILIKE '%1615%')
ORDER BY transaction_date, transaction_id
""")
for r in cur.fetchall():
    print(dict(r))
cur.close(); conn.close()
