import psycopg2
import psycopg2.extras
from decimal import Decimal

PG = "host=localhost port=5432 dbname=almsdata user=postgres password=ArrowLimousine"
RES = ['013602','013603']

conn = psycopg2.connect(PG)
cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

print('=== CHARTERS ===')
cur.execute("""
SELECT reserve_number, charter_date, client_display_name, cancelled,
       subtotal, gst_amount, gratuity_percent, extra_gratuity,
       grand_total, paid_amount, balance_owing,
       driver_gratuity, driver_total_expense,
       approved_gratuity
FROM charters
WHERE reserve_number = ANY(%s)
ORDER BY reserve_number
""", (RES,))
for r in cur.fetchall():
    print(r)

print('\n=== CHARGES ===')
cur.execute("""
SELECT reserve_number, charge_id, description, amount, rate,
       (COALESCE(amount,0)*COALESCE(rate,0)) AS line_total,
       gratuity_type, gst_amount
FROM charter_charges
WHERE reserve_number = ANY(%s)
ORDER BY reserve_number, charge_id
""", (RES,))
rows = cur.fetchall()
for r in rows:
    print(r)

print('\n=== PAYMENT TOTALS ===')
cur.execute("""
SELECT charter_id AS reserve_number, SUM(amount) AS paid
FROM charter_payments
WHERE charter_id = ANY(%s)
GROUP BY charter_id
ORDER BY charter_id
""", (RES,))
for r in cur.fetchall():
    print(r)

conn.close()
