from decimal import Decimal
import psycopg2

conn = psycopg2.connect(
    host='localhost',
    port=5432,
    dbname='almsdata',
    user='postgres',
    password='ArrowLimousine',
)
cur = conn.cursor()


def q2(v):
    return Decimal(str(v or 0)).quantize(Decimal('0.01'))

# Accurate per-charter totals via separate aggregates (avoids join multiplication)
cur.execute(
    """
    WITH charge_totals AS (
      SELECT charter_id, COALESCE(SUM(amount),0) AS charged
      FROM charter_charges
      GROUP BY charter_id
    ),
    payment_totals AS (
      SELECT c.charter_id, COALESCE(SUM(cp.amount),0) AS paid
      FROM charters c
      LEFT JOIN charter_payments cp ON cp.charter_id = c.reserve_number
      WHERE cp.payment_date BETWEEN '2012-01-01' AND '2014-12-31'
      GROUP BY c.charter_id
    ),
    base AS (
      SELECT c.charter_id,
             c.reserve_number,
             c.charter_date,
             COALESCE(c.cancelled,false) AS cancelled,
             COALESCE(ct.charged,0) AS charged,
             COALESCE(pt.paid,0) AS paid,
             COALESCE(ct.charged,0) - COALESCE(pt.paid,0) AS balance
      FROM charters c
      LEFT JOIN charge_totals ct ON ct.charter_id = c.charter_id
      LEFT JOIN payment_totals pt ON pt.charter_id = c.charter_id
      WHERE c.charter_date BETWEEN '2012-01-01' AND '2014-12-31'
    )
    SELECT COUNT(*) AS total,
           COUNT(*) FILTER (WHERE cancelled) AS cancelled_count,
           COUNT(*) FILTER (WHERE NOT cancelled) AS active_count,
           COALESCE(SUM(charged),0) AS total_charged,
           COALESCE(SUM(paid),0) AS total_paid,
           COALESCE(SUM(balance),0) AS total_balance,
           COUNT(*) FILTER (WHERE balance > 0.01) AS owing_count,
           COUNT(*) FILTER (WHERE balance < -0.01) AS credit_count,
           COUNT(*) FILTER (WHERE ABS(balance) <= 0.01) AS matched_count
    FROM base
    """
)
r = cur.fetchone()
print('total, cancelled, active =', r[0], r[1], r[2])
print('total_charged, total_paid, total_balance =', q2(r[3]), q2(r[4]), q2(r[5]))
print('owing, credit, matched =', r[6], r[7], r[8])

print('\nTop 20 balances owing:')
cur.execute(
    """
    WITH charge_totals AS (
      SELECT charter_id, COALESCE(SUM(amount),0) AS charged
      FROM charter_charges
      GROUP BY charter_id
    ),
    payment_totals AS (
      SELECT c.charter_id, COALESCE(SUM(cp.amount),0) AS paid
      FROM charters c
      LEFT JOIN charter_payments cp ON cp.charter_id = c.reserve_number
      WHERE cp.payment_date BETWEEN '2012-01-01' AND '2014-12-31'
      GROUP BY c.charter_id
    )
    SELECT c.reserve_number, c.charter_id, c.charter_date,
           COALESCE(ct.charged,0) AS charged,
           COALESCE(pt.paid,0) AS paid,
           COALESCE(ct.charged,0)-COALESCE(pt.paid,0) AS balance
    FROM charters c
    LEFT JOIN charge_totals ct ON ct.charter_id = c.charter_id
    LEFT JOIN payment_totals pt ON pt.charter_id = c.charter_id
    WHERE c.charter_date BETWEEN '2012-01-01' AND '2014-12-31'
    ORDER BY balance DESC
    LIMIT 20
    """
)
for row in cur.fetchall():
    print(row[0], row[1], row[2], q2(row[3]), q2(row[4]), q2(row[5]))

cur.close()
conn.close()
