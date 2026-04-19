import psycopg2
conn = psycopg2.connect(host='localhost',port=5432,dbname='almsdata',user='postgres',password='ArrowLimousine')
cur = conn.cursor()
for t in ['general_ledger','chart_of_accounts','receipts','charters','gl_account_year_summary']:
    cur.execute("SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name=%s)", (t,))
    ex = cur.fetchone()[0]
    print('\nTABLE', t, 'exists=', ex)
    if ex:
        cur.execute("SELECT column_name,data_type FROM information_schema.columns WHERE table_schema='public' AND table_name=%s ORDER BY ordinal_position", (t,))
        cols = cur.fetchall()
        print('cols', len(cols))
        for c,d in cols[:40]:
            print(' ', c, d)
cur.close(); conn.close()
