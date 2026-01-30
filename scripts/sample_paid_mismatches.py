import os, psycopg2
conn = psycopg2.connect(host=os.getenv('DB_HOST','localhost'),database=os.getenv('DB_NAME','almsdata'),user=os.getenv('DB_USER','postgres'),password=os.getenv('DB_PASSWORD','***REDACTED***'))
cur = conn.cursor()
cur.execute("""
WITH charge_sum AS (
  SELECT reserve_number, ROUND(SUM(COALESCE(amount,0))::numeric,2) AS charges
  FROM charter_charges
  GROUP BY reserve_number
), pay_sum AS (
  SELECT reserve_number, ROUND(SUM(COALESCE(amount,0))::numeric,2) AS paid
  FROM payments
  GROUP BY reserve_number
), base AS (
  SELECT c.charter_id, c.reserve_number,
         COALESCE(c.total_amount_due,0)::numeric(12,2) AS total_due,
         COALESCE(cs.charges,0)::numeric(12,2)          AS charges,
         COALESCE(c.paid_amount,0)::numeric(12,2)      AS paid_field,
         COALESCE(ps.paid,0)::numeric(12,2)            AS paid_sum,
         COALESCE(c.status,'') AS status,
         COALESCE(c.booking_status,'') AS booking_status,
         COALESCE(c.cancelled,false) AS cancelled
  FROM charters c
  LEFT JOIN charge_sum cs ON cs.reserve_number = c.reserve_number
  LEFT JOIN pay_sum ps    ON ps.reserve_number = c.reserve_number
)
SELECT reserve_number, charter_id, total_due, charges, paid_field, paid_sum, status
FROM base b
WHERE cancelled = false
  AND b.status NOT ILIKE '%cancel%'
  AND b.status NOT ILIKE '%quote%'
  AND b.booking_status NOT ILIKE '%quote%'
  AND ABS(b.paid_field - b.paid_sum) > 0.01
ORDER BY ABS(b.paid_field - b.paid_sum) DESC
LIMIT 10
""")
rows = cur.fetchall()
for r in rows:
    print(r)
cur.close(); conn.close()
