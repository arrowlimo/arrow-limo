import psycopg2
conn = psycopg2.connect(host='localhost', port=5432, dbname='almsdata', user='postgres', password='ArrowLimousine')
cur = conn.cursor()
for tbl in ['charters', 'payments', 'charter_payments']:
    cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name=%s ORDER BY ordinal_position", (tbl,))
    print(tbl + ':')
    print(', '.join(r[0] for r in cur.fetchall()))
    print()
conn.close()
