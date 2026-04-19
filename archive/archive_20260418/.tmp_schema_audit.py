import psycopg2
conn=psycopg2.connect(host='localhost', dbname='almsdata', user='postgres', password='ArrowLimousine', port=5432)
cur=conn.cursor()
cur.execute("""
select table_name
from information_schema.tables
where table_schema='public' and table_name ilike 'backup%charter%payments%rebuild%'
order by table_name
""")
tables=[r[0] for r in cur.fetchall()]
print('tables=',tables)
for t in ['charter_payments','payments']+tables:
    cur.execute("""
    select column_name
    from information_schema.columns
    where table_schema='public' and table_name=%s
    order by ordinal_position
    """,(t,))
    print(f"\n{t}:")
    print([r[0] for r in cur.fetchall()])
cur.close(); conn.close()
