import psycopg2
conn = psycopg2.connect('host=localhost port=5432 dbname=almsdata user=postgres password=ArrowLimousine')
cur = conn.cursor()
cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='charters' ORDER BY ordinal_position")
print('charters:', [r[0] for r in cur.fetchall()])
cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='charter_payments' ORDER BY ordinal_position")
print('charter_payments:', [r[0] for r in cur.fetchall()])
conn.close()
