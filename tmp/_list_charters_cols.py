import sys
sys.path.insert(0, r'l:\limo')
import psycopg2

conn = psycopg2.connect(host='localhost', port=5432, dbname='almsdata', user='postgres', password='ArrowLimousine')
cur = conn.cursor()
cur.execute("""
SELECT column_name
FROM information_schema.columns
WHERE table_schema='public' AND table_name='charters'
ORDER BY ordinal_position
""")
for r in cur.fetchall():
    print(r[0])
cur.close(); conn.close()
