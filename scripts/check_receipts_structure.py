import psycopg2
conn = psycopg2.connect(host='localhost', dbname='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()
cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='receipts' ORDER BY ordinal_position")
cols = [r[0] for r in cur.fetchall()]
print('Receipts columns:')
for c in cols:
    print(f'  {c}')
cur.close()
conn.close()
