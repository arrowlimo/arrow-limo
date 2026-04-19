import psycopg2
conn = psycopg2.connect(host='localhost', port=5432, dbname='almsdata', user='postgres', password='ArrowLimousine')
cur = conn.cursor()
for t in ['charters','payments','charter_payments']:
    cur.execute("select column_name, data_type from information_schema.columns where table_name=%s order by ordinal_position", (t,))
    print('TABLE', t)
    for row in cur.fetchall():
        print(row)
    print()
conn.close()
