import psycopg2
conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()
cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'clients' ORDER BY ordinal_position")
cols = cur.fetchall()
print('\nClients table columns:')
for c in cols:
    print(f'  - {c[0]}')
cur.close()
conn.close()
