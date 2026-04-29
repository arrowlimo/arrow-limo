import psycopg2
from psycopg2 import sql

params = dict(dbname='almsdata', user='postgres', password='ArrowLimousine')
hosts = ['192.168.1.176', 'localhost']
conn = None
used_host = None
for host in hosts:
    try:
        c = psycopg2.connect(host=host, connect_timeout=5, **params)
        cur = c.cursor()
        cur.execute('select current_database(), current_user')
        print('CONNECTED', host, cur.fetchone())
        conn = c
        used_host = host
        break
    except Exception as e:
        print('FAILED', host, type(e).__name__, e)
if not conn:
    raise SystemExit('no host connected')
cur = conn.cursor()
cur.execute("""
select table_schema, table_name
from information_schema.columns
where column_name in (
  'charter_id','reserve_number','charter_date','driver_hours_worked','approved_hours',
  'driver_gratuity_amount','driver_gratuity','approved_gratuity','extra_gratuity','gratuity_percent'
)
group by table_schema, table_name
having count(distinct column_name) >= 8
order by table_schema, table_name
""")
print('TABLE_CANDIDATES')
for row in cur.fetchall():
    print(row)
cur.execute("""
select table_schema, table_name, column_name, data_type
from information_schema.columns
where table_schema='public' and table_name in ('employees','charters','reservations','trips','payroll','payroll_detail')
order by table_name, ordinal_position
""")
print('SELECTED_COLUMNS')
for row in cur.fetchall():
    print(row)
conn.close()
