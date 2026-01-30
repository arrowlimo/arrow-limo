#!/usr/bin/env python3
import psycopg2

RESERVES = ('019223','019224')
LAST4 = '2198'
AUTH = '#tGl6'
EXPECTED_SPLIT = 500.00

conn = psycopg2.connect(dbname='almsdata', user='postgres', password='***REDACTED***', host='localhost')
cur = conn.cursor()

print('Charter status:')
cur.execute(
    """
    SELECT reserve_number, total_amount_due, paid_amount, balance
    FROM charters
    WHERE reserve_number IN %s
    ORDER BY reserve_number
    """,
    (RESERVES,)
)
charters = cur.fetchall()
for r, due, paid, bal in charters:
    print(f"  {r}: due={due} paid={paid} bal={bal}")

print('\nPayments for target reserves:')
cur.execute(
    """
    SELECT reserve_number, amount, payment_method, credit_card_last4, authorization_code,
           payment_key, payment_date, payment_id
    FROM payments
    WHERE reserve_number IN %s
    ORDER BY reserve_number, payment_date NULLS LAST, payment_id
    """,
    (RESERVES,)
)
rows = cur.fetchall()
for rsv, amt, method, last4, auth, pkey, pdate, pid in rows:
    print(f"  {rsv}: ${amt:.2f} {method or ''} last4={last4 or ''} auth={auth or ''} date={pdate} id={pid} key={pkey or ''}")

print('\nLooking for two $500 MC 2198 with auth #tGl6 (one per reserve)...')
cur.execute(
    """
    SELECT reserve_number, COUNT(*)
    FROM payments
    WHERE reserve_number IN %s
      AND amount = %s
      AND (payment_method = 'credit_card' OR payment_method IS NULL)
      AND (credit_card_last4 = %s OR credit_card_last4 IS NULL)
      AND (authorization_code = %s OR authorization_code IS NULL)
    GROUP BY reserve_number
    ORDER BY reserve_number
    """,
    (RESERVES, EXPECTED_SPLIT, LAST4, AUTH)
)
summary = dict(cur.fetchall()) if cur.rowcount else {}

for r in RESERVES:
    count = summary.get(r, 0)
    status = 'OK' if count >= 1 else 'MISSING'
    print(f"  {r}: $500 split payment match -> {status} (count={count})")

cur.close()
conn.close()
