import psycopg2
conn=psycopg2.connect(host='localhost',port=5432,dbname='almsdata',user='postgres',password='ArrowLimousine')
cur=conn.cursor()
interesting_tables=['charters','payments','charter_payments','income_ledger','accounting_entries','receipts','reserves','reserve','invoices']
for t in interesting_tables:
    cur.execute("""
    select column_name, data_type
    from information_schema.columns
    where table_schema='public' and table_name=%s
    order by ordinal_position
    """, (t,))
    rows=cur.fetchall()
    if rows:
        print(f'[{t}]')
        for c in rows:
            print(f'  {c[0]} | {c[1]}')
        print()
conn.close()
