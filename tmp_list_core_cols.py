import psycopg2

tables=['charters','payments','receipts','charter_charges','charter_payments','banking_transactions','vehicles']
conn=psycopg2.connect(host='localhost',database='almsdata',user='postgres',password='***REMOVED***')
cur=conn.cursor()
for t in tables:
    cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name=%s ORDER BY ordinal_position", (t,))
    cols=[r[0] for r in cur.fetchall()]
    print(f"{t}: {', '.join(cols)}")
conn.close()
