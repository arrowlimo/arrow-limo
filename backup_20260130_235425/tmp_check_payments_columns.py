import psycopg2

conn = psycopg2.connect(host='localhost', dbname='almsdata', user='postgres', password='ArrowLimousine')
cur = conn.cursor()
cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='payments' ORDER BY ordinal_position")
print('Payments table columns:')
for r in cur.fetchall():
    print(f'  {r[0]}')
cur.close()
conn.close()
