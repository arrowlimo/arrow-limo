#!/usr/bin/env python3
import psycopg2

conn = psycopg2.connect(
    host='localhost',
    port=5432,
    database='almsdata',
    user='postgres',
    password='ArrowLimousine'
)
cur = conn.cursor()

cur.execute('select count(*) from charter_payments')
print('cp_total', cur.fetchone()[0])

cur.execute('select count(*) from charter_payments where payment_id is null')
print('cp_payment_id_null', cur.fetchone()[0])

cur.execute('select count(*) from charter_payments cp join payments p on p.payment_id=cp.payment_id')
print('cp_join_payments', cur.fetchone()[0])

cur.execute('''
select count(*)
from charter_payments cp
left join payments p on p.payment_id=cp.payment_id
where cp.payment_id is not null and p.payment_id is null
''')
print('cp_payment_id_orphans', cur.fetchone()[0])

cur.execute('''
select count(*)
from charter_payments
where extract(year from payment_date)=2012
''')
print('cp_2012_count', cur.fetchone()[0])

cur.execute('''
select count(*)
from charter_payments cp
join payments p on p.payment_id=cp.payment_id
where extract(year from cp.payment_date)=2012
''')
print('cp_2012_join_payments', cur.fetchone()[0])

cur.close()
conn.close()
