"""
Debug: Check if charter_payments.charter_id is linking correctly to charter_charges.
"""
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

def q2(value):
    return Decimal(str(value or 0)).quantize(Decimal('0.01'))

print("=" * 80)
print("CHARTER_PAYMENTS LINKING VERIFICATION")
print("=" * 80)

# Check charter_payments data types and sample values
print("\nSample charter_payments rows:")
cur.execute("""
    SELECT id, payment_id, charter_id, amount, payment_date, source
    FROM charter_payments
    WHERE EXTRACT(YEAR FROM payment_date) = 2012
    LIMIT 5
""")
print(f"{'ID':<6} {'payment_id':<12} {'charter_id':<15} {'Amount':<12} {'Date':<12} {'Source':<20}")
print("-" * 85)
for row in cur.fetchall():
    print(f"{row[0]:<6} {row[1]:<12} {row[2]:<15} ${q2(row[3]):<11} {row[4]} {row[5]:<20}")

# Check if charter_id values in charter_payments exist in charters table
print("\n\nChecking if charter_id values in charter_payments exist in charters table:")
cur.execute("""
    SELECT COUNT(*) as total_payments,
           COUNT(CAST(charter_id AS INTEGER)) as casts_ok,
           SUM(CASE WHEN CAST(charter_id AS INTEGER) IN (SELECT charter_id FROM charters) THEN 1 ELSE 0 END) as found_in_charters
    FROM charter_payments
    WHERE EXTRACT(YEAR FROM payment_date) IN (2012, 2013)
""")
total, casts, found = cur.fetchone()
print(f"  Total Payments: {total}")
print(f"  Can cast to INT: {casts}")
print(f"  Found in charters table: {found}")

# Check for payments with unmatched charter_ids
print("\n\nSample payments with UNMATCHED charter_ids:")
cur.execute("""
    SELECT cp.charter_id, COUNT(*), SUM(cp.amount)
    FROM charter_payments cp
    LEFT JOIN charters c ON CAST(cp.charter_id AS INTEGER) = c.charter_id
    WHERE EXTRACT(YEAR FROM cp.payment_date) IN (2012, 2013)
      AND c.charter_id IS NULL
    GROUP BY cp.charter_id
    LIMIT 10
""")
unmatched = cur.fetchall()
if unmatched:
    print(f"{'charter_id':<20} {'Count':<10} {'Total Amount':<15}")
    print("-" * 45)
    for cid, count, amount in unmatched:
        print(f"{cid:<20} {count:<10} ${q2(amount):<14}")
else:
    print("  ✓ All charter_ids in payments match charters table")

# Now check the reverse: charters that have charges but NO payments
print("\n\nCharters in 2012/2013 with charges but NO payments:")
cur.execute("""
    SELECT c.charter_id, COUNT(cc.charge_id), SUM(cc.amount)
    FROM charters c
    JOIN charter_charges cc ON c.charter_id = cc.charter_id
    LEFT JOIN charter_payments cp ON c.charter_id = CAST(cp.charter_id AS INTEGER)
    WHERE EXTRACT(YEAR FROM c.charter_date) IN (2012, 2013)
      AND cp.id IS NULL
    GROUP BY c.charter_id
    ORDER BY SUM(cc.amount) DESC
    LIMIT 10
""")
orphans = cur.fetchall()
print(f"Found {len(orphans)} charters with charges but no payments (showing top 10):")
print(f"{'Charter ID':<15} {'Charge Count':<15} {'Total Charged':<15}")
print("-" * 45)
for cid, cc, amt in orphans:
    print(f"{cid:<15} {cc:<15} ${q2(amt):<14}")

cur.close()
conn.close()
