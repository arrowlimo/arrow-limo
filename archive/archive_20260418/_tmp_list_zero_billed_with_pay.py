import psycopg2
import psycopg2.extras
from decimal import Decimal

conn = psycopg2.connect('host=localhost port=5432 dbname=almsdata user=postgres password=ArrowLimousine')
cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
cur.execute("""
WITH p AS (
  SELECT charter_id AS reserve_number, SUM(amount) AS paid_total
  FROM charter_payments
  WHERE charter_id IS NOT NULL AND charter_id <> ''
  GROUP BY charter_id
)
SELECT c.reserve_number, c.charter_date, c.client_display_name, c.cancelled,
       COALESCE(c.grand_total,0) AS billed_total,
       COALESCE(p.paid_total,0) AS paid_total,
       COALESCE(c.nrr_received,false) AS nrr_received,
       COALESCE(c.nrr_amount,0) AS nrr_amount,
       COALESCE(c.nrd_received,false) AS nrd_received,
       COALESCE(c.nrd_amount,0) AS nrd_amount
FROM charters c
JOIN p ON p.reserve_number = c.reserve_number
WHERE c.charter_date >= '2007-01-01' AND c.charter_date < '2019-01-01'
  AND COALESCE(c.grand_total,0) = 0
  AND ABS(COALESCE(p.paid_total,0)) > 0.02
ORDER BY ABS(COALESCE(p.paid_total,0)) DESC, c.reserve_number
""")
rows = cur.fetchall()
print(f"rows={len(rows)}")
for r in rows:
    print(
        r['reserve_number'], str(r['charter_date'])[:10], r['client_display_name'],
        'cancelled=', r['cancelled'],
        'paid=', Decimal(str(r['paid_total'])),
        'nrr=', r['nrr_received'], Decimal(str(r['nrr_amount'])),
        'nrd=', r['nrd_received'], Decimal(str(r['nrd_amount']))
    )
conn.close()
