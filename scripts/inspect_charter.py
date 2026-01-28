"""
Inspect charter by reserve_number: show charter record, linked charges (by reserve_number), NULL-reserve artifacts for the charter_id, and payments.
Usage: python scripts/inspect_charter.py RESERVE_NUMBER
"""
import os
import sys
import psycopg2

if len(sys.argv) < 2:
    print("Usage: python scripts/inspect_charter.py RESERVE_NUMBER")
    sys.exit(1)

r = sys.argv[1]

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

print(f"=== Charter {r} ===")
cur.execute(
    """
    SELECT charter_id, reserve_number, status, charter_date, total_amount_due, paid_amount, balance
    FROM charters
    WHERE reserve_number = %s
    """,
    (r,),
)
charter = cur.fetchone()
print(charter)

print("\n=== Charges by reserve_number ===")
cur.execute(
    """
    SELECT charge_id, amount, description, charge_type, account_number
    FROM charter_charges
    WHERE reserve_number = %s
    ORDER BY amount DESC
    """,
    (r,),
)
rows = cur.fetchall()
print(f"count={len(rows)} sum={sum([row[1] for row in rows]) if rows else 0}")
for row in rows:
    print(row)

print("\n=== NULL-reserve artifacts for charter_id ===")
cur.execute(
    """
    SELECT charge_id, amount, description, charge_type
    FROM charter_charges
    WHERE (reserve_number IS NULL OR reserve_number = '')
      AND charter_id = (SELECT charter_id FROM charters WHERE reserve_number = %s)
    ORDER BY amount DESC
    """,
    (r,),
)
rows = cur.fetchall()
print(f"count={len(rows)} sum={sum([row[1] for row in rows]) if rows else 0}")
for row in rows:
    print(row)

print("\n=== Payments ===")
cur.execute(
    """
    SELECT payment_id, amount, payment_date, payment_method
    FROM payments
    WHERE reserve_number = %s
    ORDER BY amount DESC
    """,
    (r,),
)
rows = cur.fetchall()
print(f"count={len(rows)} sum={sum([row[1] for row in rows]) if rows else 0}")
for row in rows:
    print(row)

cur.close()
conn.close()
