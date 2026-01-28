import psycopg2

conn = psycopg2.connect(host='localhost',dbname='almsdata',user='postgres',password='***REMOVED***')
cur = conn.cursor()
cur.execute("SELECT column_name,data_type FROM information_schema.columns WHERE table_name='charter_credit_ledger' ORDER BY ordinal_position")
print('charter_credit_ledger columns:')
for name, dtype in cur.fetchall():
    print(f" - {name}: {dtype}")
cur.close(); conn.close()
