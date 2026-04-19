import psycopg2
from psycopg2.extras import RealDictCursor

conn = psycopg2.connect("dbname=almsdata user=postgres host=localhost password=ArrowLimousine")
cur = conn.cursor(cursor_factory=RealDictCursor)

print("=== IDENTIFY CARRY-FORWARD RESERVES WITH PAYMENTS ===\n")

# Get list of all zero-billed charters with payments
cur.execute("""
SELECT 
  c.reserve_number,
  c.charter_date,
  COUNT(cp.payment_id) as payment_count,
  SUM(cp.amount) as total_payment_amount
FROM charters c
JOIN charter_payments cp ON cp.charter_id = c.reserve_number
WHERE c.grand_total = 0
GROUP BY c.reserve_number, c.charter_date
ORDER BY c.charter_date DESC
""")

rows = cur.fetchall()
print(f"Found {len(rows)} zero-billed charters with payments:\n")

total_payment_amount = 0
reserve_list = []

for i, row in enumerate(rows[:20], 1):  # Show first 20
    res_no = row['reserve_number']
    reserve_list.append(res_no)
    payment_amt = row['total_payment_amount']
    total_payment_amount += payment_amt
    
    charter_date = row['charter_date'] if isinstance(row['charter_date'], str) else str(row['charter_date'])
    print(f"{i}. {res_no} ({charter_date}): {row['payment_count']} payments, ${payment_amt:,.2f}")

if len(rows) > 20:
    print(f"... and {len(rows) - 20} more\n")

print(f"\n=== UNLINK ALL PAYMENTS FROM ZERO-BILLED CARRIES ===\n")

# Get ALL reserve numbers
cur.execute("""
SELECT c.reserve_number
FROM charters c
WHERE c.grand_total = 0
  AND EXISTS (SELECT 1 FROM charter_payments cp WHERE cp.charter_id = c.reserve_number)
""")

all_carries = [r['reserve_number'] for r in cur.fetchall()]
print(f"Total carry-forward reserves with payments: {len(all_carries)}")

# Unlink all payments
cur.execute("""
UPDATE charter_payments
SET charter_id = NULL, source = 'carry_forward_unlinked_20260322'
WHERE charter_id IN (
  SELECT c.reserve_number
  FROM charters c
  WHERE c.grand_total = 0
    AND EXISTS (SELECT 1 FROM charter_payments cp WHERE cp.charter_id = c.reserve_number)
)
""")

unlinkd_count = cur.rowcount
print(f"Unlinked {unlinkd_count} payment rows\n")

conn.commit()

# Verify
print("=== VERIFICATION ===\n")
cur.execute("""
SELECT COUNT(*) as remaining
FROM charters c
WHERE c.grand_total = 0
  AND EXISTS (SELECT 1 FROM charter_payments cp WHERE cp.charter_id = c.reserve_number)
""")

remaining = cur.fetchone()['remaining']
print(f"Zero-billed charters with payments: {remaining}")
if remaining == 0:
    print("✅ ALL CARRY-FORWARD ANOMALIES CLEANED UP")
else:
    print(f"❌ {remaining} anomalies still remaining")

# Check unlinked payment count
cur.execute("""
SELECT COUNT(*) as unlinked_count, SUM(amount) as unlinked_amount
FROM charter_payments
WHERE source = 'carry_forward_unlinked_20260322'
""")

result = cur.fetchone()
print(f"\nUnlinked carry-forward payments: {result['unlinked_count']} payments, ${result['unlinked_amount']:,.2f}")

conn.close()
