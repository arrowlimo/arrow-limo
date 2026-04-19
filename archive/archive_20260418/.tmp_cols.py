import psycopg2
conn=psycopg2.connect(host='localhost', dbname='almsdata', user='postgres', password='ArrowLimousine', port=5432)
cur=conn.cursor()
cur.execute("""
select column_name
from information_schema.columns
where table_schema='public' and table_name='payments'
order by ordinal_position
""")
print([r[0] for r in cur.fetchall()])
cur.close(); conn.close()
