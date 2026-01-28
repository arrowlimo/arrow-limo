import psycopg2
conn=psycopg2.connect(host='localhost',database='almsdata',user='postgres',password='***REMOVED***')
cur=conn.cursor()
cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='payments' ORDER BY ordinal_position")
print('\n'.join(r[0] for r in cur.fetchall()))
conn.close()
