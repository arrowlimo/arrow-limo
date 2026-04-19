import psycopg2
conn = psycopg2.connect(host="localhost", dbname="almsdata", user="postgres", password="ArrowLimousine", port=5432)
cur = conn.cursor()
cur.execute('''
select table_schema, table_name
from information_schema.tables
where table_name = 'backup_charter_payments_before_rebuild'
order by table_schema, table_name
''')
rows = cur.fetchall()
print(rows)
cur.close(); conn.close()
