import psycopg2
conn = psycopg2.connect(host='localhost', port=5432, dbname='almsdata', user='postgres', password='ArrowLimousine')
cur = conn.cursor()
cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='vendor_accounts' ORDER BY ordinal_position")
print([r[0] for r in cur.fetchall()])
cur.close(); conn.close()
