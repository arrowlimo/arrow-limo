import psycopg2
conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()
cur.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_name='payments' ORDER BY ordinal_position")
for col, typ in cur.fetchall():
    print(f'{col:30} {typ}')
cur.close()
conn.close()
