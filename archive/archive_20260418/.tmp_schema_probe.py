import psycopg2
conn = psycopg2.connect(host="localhost", dbname="almsdata", user="postgres", password="ArrowLimousine", port=5432)
cur = conn.cursor()
cur.execute('''
select table_schema, table_name
from information_schema.tables
where table_schema not in ('pg_catalog','information_schema')
  and (table_name ilike '%charter%' or table_name ilike '%payment%' or table_name ilike '%reserve%')
order by table_schema, table_name
''')
for r in cur.fetchall():
    print(r)
cur.close()
conn.close()
