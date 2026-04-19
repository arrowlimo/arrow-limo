import psycopg2
from psycopg2.extras import RealDictCursor
conn=psycopg2.connect(dbname='almsdata', user='postgres', password='ArrowLimousine', host='localhost', port=5432)
cur=conn.cursor(cursor_factory=RealDictCursor)
cur.execute("""
SELECT account_code, account_name, account_type, is_business_expense
FROM chart_of_accounts
WHERE account_code IN ('5900','5710','5720','5715','6800')
ORDER BY account_code
""")
print(cur.fetchall())
cur.close(); conn.close()
