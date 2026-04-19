import psycopg2
conn = psycopg2.connect(host="localhost", dbname="almsdata", user="postgres", password="ArrowLimousine", port=5432)
cur = conn.cursor()
cur.execute('''
select table_schema, table_name
from information_schema.tables
where table_schema='public' and table_name ilike '%before%rebuild%'
order by table_name
''')
for r in cur.fetchall():
    print(r)
cur.close(); conn.close()
