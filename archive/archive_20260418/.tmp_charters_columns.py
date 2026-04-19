import psycopg2
conn=psycopg2.connect(host='localhost', port=5432, dbname='almsdata', user='postgres', password='ArrowLimousine')
cur=conn.cursor()
cur.execute("""
select column_name, data_type
from information_schema.columns
where table_schema='public'
  and table_name='charters'
  and (
    column_name ilike '%total%'
    or column_name ilike '%subtotal%'
    or column_name ilike '%gst%'
    or column_name ilike '%tax%'
    or column_name ilike '%gratuity%'
    or column_name ilike '%tip%'
    or column_name ilike '%paid%'
    or column_name ilike '%balance%'
    or column_name ilike '%status%'
    or column_name ilike '%cancel%'
    or column_name ilike '%deposit%'
    or column_name ilike '%invoice%'
    or column_name ilike '%amount%'
    or column_name ilike '%fare%'
    or column_name ilike '%rate%'
  )
order by ordinal_position
""")
for column_name, data_type in cur.fetchall():
    print(f"{column_name}\t{data_type}")
conn.close()
