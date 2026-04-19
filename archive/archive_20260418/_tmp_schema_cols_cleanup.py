import psycopg2
from psycopg2.extras import RealDictCursor
conn=psycopg2.connect(dbname='almsdata', user='postgres', password='ArrowLimousine', host='localhost', port=5432)
cur=conn.cursor(cursor_factory=RealDictCursor)
cur.execute("""
SELECT column_name
FROM information_schema.columns
WHERE table_schema='public' AND table_name='receipts'
ORDER BY ordinal_position
""")
print('receipts columns:')
print([r['column_name'] for r in cur.fetchall()])
cur.execute("""
SELECT column_name
FROM information_schema.columns
WHERE table_schema='public' AND table_name='banking_transactions'
ORDER BY ordinal_position
""")
print('\nbanking_transactions columns sample:')
cols=[r['column_name'] for r in cur.fetchall()]
print(cols)
cur.close(); conn.close()
