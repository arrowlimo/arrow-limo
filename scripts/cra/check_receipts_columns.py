import psycopg2
c = psycopg2.connect(host='localhost', dbname='almsdata', user='postgres', password='***REDACTED***')
cur = c.cursor()
cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'receipts' ORDER BY ordinal_position")
print('\n'.join([r[0] for r in cur.fetchall()]))
c.close()
