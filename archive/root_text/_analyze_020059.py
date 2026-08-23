import json

from _db_connect import connect_db

conn = connect_db()
cur = conn.cursor()

print("=== CHARTER_PAYMENTS (by reserve/id) ===")
cur.execute("SELECT * FROM charter_payments WHERE charter_id='020059' OR charter_id='19203'")
rows = cur.fetchall()
cols = [d[0] for d in cur.description]
for r in rows:
    print(' ', dict(zip(cols, r, strict=False)))
if not rows:
    print("  (no rows)")

print("\n=== PAYMENTS matching 181.45 ===")
cur.execute("SELECT reserve_number, amount, payment_method, payment_date FROM payments WHERE amount=181.45 LIMIT 5")
rows2 = cur.fetchall()
print(rows2 or "(none)")

print("\n=== CHARTER_DATA JSON ===")
cur.execute("SELECT charter_data FROM charters WHERE charter_id=19203")
r3 = cur.fetchone()
cd = r3[0] if r3 else None
print(json.dumps(cd, indent=2) if cd else None)

print("\n=== ALL CHARTERS FIELDS FOR 020059 ===")
cur.execute("""
    SELECT charter_id, reserve_number, nrd_amount, nrd_received,
           nrr_amount, nrr_received, paid_amount, payment_totals,
           subtotal, gst_amount, grand_total, amount_paid, balance_owing,
           gratuity_percent, extra_gratuity, approved_gratuity,
           hourly_rate, quoted_hours, charter_fee_type,
           driver_gratuity, driver_base_pay, driver_total_expense
    FROM charters WHERE charter_id=19203
""")
r4 = cur.fetchone()
cols4 = [d[0] for d in cur.description]
for c, v in zip(cols4, r4, strict=False):
    print(f"  {c}: {v}")

cur.close()
conn.close()
