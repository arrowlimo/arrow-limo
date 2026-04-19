import psycopg2
import psycopg2.extras

PG = "host=localhost port=5432 dbname=almsdata user=postgres password=ArrowLimousine"
TARGETS = ['013603','014215','001188','001918','013963']

conn = psycopg2.connect(PG)
cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

print('Before:')
cur.execute("""
WITH p AS (
  SELECT charter_id AS reserve_number, SUM(amount) AS paid_total
  FROM charter_payments
  WHERE charter_id IS NOT NULL AND charter_id <> ''
  GROUP BY charter_id
)
SELECT c.reserve_number, c.grand_total, c.paid_amount, c.balance_owing,
       COALESCE(p.paid_total,0) AS calc_paid,
       COALESCE(c.grand_total,0)-COALESCE(p.paid_total,0) AS calc_balance
FROM charters c
LEFT JOIN p ON p.reserve_number = c.reserve_number
WHERE c.reserve_number = ANY(%s)
ORDER BY c.reserve_number
""", (TARGETS,))
for r in cur.fetchall():
    print(r)

cur.execute("""
WITH p AS (
  SELECT charter_id AS reserve_number, SUM(amount) AS paid_total
  FROM charter_payments
  WHERE charter_id IS NOT NULL AND charter_id <> ''
  GROUP BY charter_id
)
UPDATE charters c
SET paid_amount = COALESCE(p.paid_total,0),
    balance_owing = COALESCE(c.grand_total,0)-COALESCE(p.paid_total,0)
FROM p
WHERE c.reserve_number = p.reserve_number
  AND c.reserve_number = ANY(%s)
""", (TARGETS,))

# for targets with no linked payments, set paid=0 and balance=grand_total
cur.execute("""
UPDATE charters c
SET paid_amount = 0,
    balance_owing = COALESCE(c.grand_total,0)
WHERE c.reserve_number = ANY(%s)
  AND NOT EXISTS (
    SELECT 1 FROM charter_payments cp
    WHERE cp.charter_id = c.reserve_number
  )
""", (TARGETS,))

conn.commit()

print('\nAfter:')
cur.execute("""
WITH p AS (
  SELECT charter_id AS reserve_number, SUM(amount) AS paid_total
  FROM charter_payments
  WHERE charter_id IS NOT NULL AND charter_id <> ''
  GROUP BY charter_id
)
SELECT c.reserve_number, c.grand_total, c.paid_amount, c.balance_owing,
       COALESCE(p.paid_total,0) AS calc_paid,
       COALESCE(c.grand_total,0)-COALESCE(p.paid_total,0) AS calc_balance
FROM charters c
LEFT JOIN p ON p.reserve_number = c.reserve_number
WHERE c.reserve_number = ANY(%s)
ORDER BY c.reserve_number
""", (TARGETS,))
for r in cur.fetchall():
    print(r)

conn.close()
