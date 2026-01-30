import os, psycopg2, sys
reserve = sys.argv[1] if len(sys.argv)>1 else None
if not reserve:
    print('usage: debug_single_charter.py RESERVE')
    raise SystemExit(1)
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
)
SELECT c.reserve_number, c.charter_id, c.total_amount_due, cs.charges, c.paid_amount, ps.paid, c.balance, c.status, c.booking_status, c.cancelled
FROM charters c
LEFT JOIN charge_sum cs ON cs.reserve_number = c.reserve_number
LEFT JOIN pay_sum ps ON ps.reserve_number = c.reserve_number
WHERE c.reserve_number=%s
""", (reserve,))
row = cur.fetchone()
print(row)
cur.close(); conn.close()
