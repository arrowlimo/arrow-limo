import psycopg2
from psycopg2.extras import RealDictCursor
conn=psycopg2.connect(dbname='almsdata', user='postgres', password='ArrowLimousine', host='localhost', port=5432)
cur=conn.cursor(cursor_factory=RealDictCursor)
cur.execute("""
SELECT account_code, account_name, account_type
FROM chart_of_accounts
WHERE account_name ILIKE '%insur%' OR account_name ILIKE '%lease%' OR account_name ILIKE '%registr%' OR account_name ILIKE '%license%' OR account_name ILIKE '%fuel%'
ORDER BY account_code
""")
for r in cur.fetchall():
    print(dict(r))
cur.close(); conn.close()
