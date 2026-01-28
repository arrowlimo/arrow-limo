import psycopg2
import os
from decimal import Decimal

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

reserve = "015918"
charter_id = 14805
missing_amount = Decimal('156.00')

# Insert the missing charge
cur.execute("""
    INSERT INTO charter_charges (charter_id, reserve_number, description, amount, created_at)
    VALUES (%s, %s, %s, %s, NOW())
    RETURNING charge_id
""", (charter_id, reserve, "Service Fee (Adjustment)", float(missing_amount)))

charge_id = cur.fetchone()[0]
conn.commit()

print(f"✅ Added charge {charge_id}: ${missing_amount:.2f} to charter {reserve}")

# Verify
cur.execute("""
    SELECT SUM(amount) FROM charter_charges WHERE reserve_number = %s
""", (reserve,))
total_charges = cur.fetchone()[0] or 0

cur.execute("""
    SELECT total_amount_due FROM charters WHERE reserve_number = %s
""", (reserve,))
total_due = cur.fetchone()[0]

print(f"  Total charges now: ${total_charges:.2f}")
print(f"  Total due:        ${total_due:.2f}")
if abs(total_charges - total_due) < 0.01:
    print(f"✅ PARITY ACHIEVED!")
else:
    print(f"⚠️  Still short: ${total_due - total_charges:.2f}")

cur.close()
conn.close()
