import psycopg2
conn=psycopg2.connect(dbname='almsdata', user='postgres', password='ArrowLimousine', host='localhost', port=5432)
cur=conn.cursor()
cur.execute("SELECT column_name,data_type FROM information_schema.columns WHERE table_name='banking_transactions' ORDER BY ordinal_position")
for c,t in cur.fetchall():
    print(f"{c} {t}")
conn.close()
