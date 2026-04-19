import psycopg2
import psycopg2.extras

conn = psycopg2.connect('host=localhost port=5432 dbname=almsdata user=postgres password=ArrowLimousine')
cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

print('=== CHARTER 007282 ===')
cur.execute("""
SELECT reserve_number, charter_date, client_display_name, subtotal, gst_amount,
       grand_total, total_amount_due, paid_amount, balance_owing,
       gratuity_percent, driver_gratuity, approved_gratuity
FROM charters
WHERE reserve_number='007282'
""")
for r in cur.fetchall():
    print(r)

print('\n=== CHARGES 007282 ===')
cur.execute("""
SELECT charge_id, description, amount, rate, sequence, category
FROM charter_charges
WHERE reserve_number='007282'
ORDER BY charge_id
""")
for r in cur.fetchall():
    print(r)

print('\n=== PAYMENTS 007282 ===')
cur.execute("""
SELECT id, amount, payment_date, payment_method, payment_key, source
FROM charter_payments
WHERE charter_id='007282'
ORDER BY id
""")
for r in cur.fetchall():
    print(r)

print('\n=== RAW CHARGE SUMS ===')
cur.execute("""
SELECT COUNT(*) AS rows,
       SUM(COALESCE(amount,0)) AS sum_amount_only,
       SUM(COALESCE(amount,0) * COALESCE(rate,0)) AS sum_amount_times_rate
FROM charter_charges
WHERE reserve_number='007282'
""")
for r in cur.fetchall():
    print(r)

conn.close()
