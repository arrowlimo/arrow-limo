import psycopg2
c = psycopg2.connect(host='localhost', dbname='almsdata', user='postgres', password='ArrowLimousine')
cur = c.cursor()
cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='charters' ORDER BY ordinal_position LIMIT 20")
print('\n'.join(r[0] for r in cur.fetchall()))
