import os, psycopg2
conn=psycopg2.connect(host=os.getenv('DB_HOST','localhost'),dbname=os.getenv('DB_NAME','almsdata'),user=os.getenv('DB_USER','postgres'),password=os.getenv('DB_PASSWORD','***REMOVED***'))
cur=conn.cursor()
cur.execute("SELECT column_name,data_type FROM information_schema.columns WHERE table_schema='public' AND table_name='receipts' ORDER BY ordinal_position")
for r in cur.fetchall():
    print(r)
cur.close(); conn.close()
