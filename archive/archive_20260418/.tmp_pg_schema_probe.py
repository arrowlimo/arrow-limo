import psycopg2
conn=psycopg2.connect(host='localhost',port=5432,dbname='almsdata',user='postgres',password='ArrowLimousine')
cur=conn.cursor()
print('TABLES WITH reserve/payment/charter names:')
cur.execute("""
select table_schema, table_name
from information_schema.tables
where table_schema='public'
  and (
    table_name ilike '%charter%'
    or table_name ilike '%payment%'
    or table_name ilike '%receipt%'
    or table_name ilike '%ledger%'
    or table_name ilike '%account%'
    or table_name ilike '%reserve%'
  )
order by table_name
""")
for r in cur.fetchall():
    print(r)
print('\nCOLUMNS OF INTEREST:')
cur.execute("""
select table_name, column_name, data_type
from information_schema.columns
where table_schema='public'
  and (
    column_name ilike '%reserve%'
    or column_name ilike '%payment%'
    or column_name ilike '%charter%'
    or column_name ilike '%receipt%'
    or column_name ilike '%ledger%'
    or column_name ilike '%balance%'
    or column_name ilike '%invoice%'
    or column_name ilike '%deposit%'
    or column_name ilike '%total%'
    or column_name ilike '%status%'
    or column_name ilike '%note%'
  )
order by table_name, ordinal_position
""")
for r in cur.fetchall():
    print(r)
conn.close()
