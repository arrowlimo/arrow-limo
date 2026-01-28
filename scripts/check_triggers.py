import psycopg2
conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()
cur.execute("SELECT tgname FROM pg_trigger WHERE tgrelid = 'banking_transactions'::regclass")
triggers = cur.fetchall()
print('Triggers on banking_transactions:')
for t in triggers:
    print(f'  - {t[0]}')
cur.close()
conn.close()
