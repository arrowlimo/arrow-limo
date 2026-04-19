import psycopg2
conn = psycopg2.connect(host='localhost', port=5432, dbname='almsdata', user='postgres', password='ArrowLimousine')
cur = conn.cursor()
cur.execute('SELECT column_name FROM information_schema.columns WHERE table_schema=\'public\' AND table_name=\'banking_transactions\' ORDER BY ordinal_position')
for (name,) in cur.fetchall():
    print(name)
cur.close()
conn.close()
