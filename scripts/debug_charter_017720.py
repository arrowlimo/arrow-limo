#!/usr/bin/env python
import psycopg2
from decimal import Decimal
from collections import defaultdict

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

reserve = '017720'
print('='*100)
print('Charter details for', reserve)
print('='*100)
cur.execute("""
SELECT reserve_number, account_number, charter_date, total_amount_due, paid_amount, balance, status
FROM charters WHERE reserve_number=%s
""", (reserve,))
row = cur.fetchone()
print(row)

print('\nCharges breakdown from charter_charges:')
cur.execute("""
SELECT COALESCE(charge_type,'(null)'), ROUND(SUM(amount)::numeric,2) 
FROM charter_charges WHERE reserve_number=%s GROUP BY 1 ORDER BY 2 DESC
""", (reserve,))
for r in cur.fetchall():
    print('  ', r)
cur.execute("SELECT ROUND(SUM(amount)::numeric,2) FROM charter_charges WHERE reserve_number=%s", (reserve,))
print('TOTAL CHARGES (from charter_charges):', cur.fetchone()[0])

print('\nLinked payments via charter_payments:')
cur.execute("""
SELECT cp.payment_id, COALESCE(p.payment_amount,p.amount) amt, p.payment_date, 
       COALESCE(p.payment_method,p.qb_payment_type) method,
       p.payment_key, p.reference_number, p.check_number, p.authorization_code
FROM charter_payments cp
JOIN payments p ON p.payment_id = cp.payment_id
WHERE cp.charter_id = %s
ORDER BY p.payment_date, cp.payment_id
""", (reserve,))
rows = cur.fetchall()
by_type = defaultdict(Decimal)
by_key = defaultdict(int)
linked_total = Decimal('0')
for (pid, amt, dt, method, key, ref, chk, auth) in rows:
    amt = Decimal(amt or 0)
    linked_total += amt
    if key is None:
        kind = 'NULL'
    elif key.startswith('LMSDEP:'):
        kind = 'LMSDEP'
    elif key.startswith('BTX:'):
        kind = 'BTX'
    elif key.startswith('SQ:'):
        kind = 'SQ'
    elif key.isdigit():
        kind = 'NUMERIC'
    else:
        kind = 'OTHER'
    by_type[kind] += amt
    by_key[key or 'NULL'] += 1
    print(f"  pid={pid} date={dt} amt={amt} method={method} key={key} ref={ref} chk={chk} auth={auth}")
print('LINKED TOTAL:', linked_total)

print('\nRaw charter_payments rows (including any without matching payments):')
cur.execute("""
SELECT id, charter_id, payment_id, amount
FROM charter_payments
WHERE charter_id = %s
ORDER BY id
""", (reserve,))
raw = cur.fetchall()
raw_total = Decimal('0')
for r in raw:
    print('  ', r)
    raw_total += Decimal(r[3] or 0)
print('RAW charter_payments SUM:', raw_total)

print('\nCounts by key type:')
for k,v in by_type.items():
    print(f'  {k}: {v}')

print('\nDirect payments where payments.reserve_number=017720 (not necessarily linked via charter_payments):')
cur.execute("""
SELECT payment_id, COALESCE(payment_amount,amount) amt, payment_date, payment_method, payment_key
FROM payments WHERE reserve_number=%s
ORDER BY payment_date
""", (reserve,))
rows2 = cur.fetchall()
print('COUNT:', len(rows2))
print('SUM:', sum(Decimal(r[1] or 0) for r in rows2))
for r in rows2[:30]:
    print('  ', r)

print('\n$102 payments week before 2023-07-01 (context check):')
cur.execute("""
SELECT payment_id, COALESCE(payment_amount,amount) amt, payment_date, payment_method, payment_key, reserve_number
FROM payments 
WHERE payment_date BETWEEN '2023-06-23' AND '2023-07-01'
  AND COALESCE(payment_amount,amount) BETWEEN 101.50 AND 102.50
ORDER BY payment_date, payment_id
LIMIT 200
""")
rows3 = cur.fetchall()
print('COUNT:', len(rows3), 'SUM:', sum(Decimal(r[1] or 0) for r in rows3))
for r in rows3[:25]:
    print('  ', r)

cur.close(); conn.close()
print('\nDone.')
