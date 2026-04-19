import psycopg2
from psycopg2.extras import RealDictCursor
from decimal import Decimal

conn = psycopg2.connect("dbname=almsdata user=postgres host=localhost password=ArrowLimousine")
cur = conn.cursor(cursor_factory=RealDictCursor)

print("=== FINAL CHARTER REVENUE & PAYMENT RECONCILIATION ===\n")

# Get by year
cur.execute("""
WITH p AS (
  SELECT charter_id, SUM(amount) AS paid_total
  FROM charter_payments
  GROUP BY charter_id
)
SELECT 
  COUNT(*) as total_charters,
  SUM(grand_total) as total_invoiced,
  COALESCE(SUM(p.paid_total), 0) as total_paid,
  SUM(grand_total) - COALESCE(SUM(p.paid_total), 0) as total_difference
FROM charters c
LEFT JOIN p ON p.charter_id = c.reserve_number
WHERE grand_total > 0
""")

row = cur.fetchone()

total_invoiced = Decimal(str(row['total_invoiced'])) if row['total_invoiced'] else Decimal('0')
total_paid = Decimal(str(row['total_paid'])) if row['total_paid'] else Decimal('0')
total_difference = Decimal(str(row['total_difference'])) if row['total_difference'] else Decimal('0')
collection_pct = float(total_paid) / float(total_invoiced) * 100.0 if total_invoiced > 0 else 0

print(f"Total Billed Charters: {row['total_charters']:,}")
print(f"Total Charter Invoicing: ${float(total_invoiced):,.2f}")
print(f"Total Payments Received: ${float(total_paid):,.2f}")
print(f"Outstanding Balance: ${float(total_difference):,.2f}")
print(f"Collection Rate: {collection_pct:.1f}%")

# Check data quality
print("\n=== DATA QUALITY CHECK ===\n")

cur.execute("""
SELECT COUNT(*) as count
FROM charters c
WHERE grand_total = 0
  AND EXISTS (SELECT 1 FROM charter_payments cp WHERE cp.charter_id = c.reserve_number)
""")

anomalies = cur.fetchone()['count']
print(f"Zero-billed charters with payments: {anomalies}")
if anomalies == 0:
    print("✅ PASS - No anomalies")
else:
    print(f"❌ FAIL - {anomalies} anomalies")

# Show unlinked carry-forward payments
cur.execute("""
SELECT COUNT(*) as count, SUM(amount) as amount
FROM charter_payments
WHERE charter_id IS NULL
""")

unlinked = cur.fetchone()
print(f"\nUnlinked payments (no charter): {unlinked['count']} payments, ${unlinked['amount']:,.2f}")

# Final billed-charter rule
print("\n=== BILLED-CHARTER BALANCE RULE (ALL DATA) ===\n")
cur.execute("""
WITH p AS (
  SELECT charter_id, SUM(amount) AS paid_total
  FROM charter_payments
  WHERE charter_id IS NOT NULL
  GROUP BY charter_id
)
SELECT 
  COUNT(*) as total_billed,
  SUM(CASE WHEN ABS(grand_total - COALESCE(p.paid_total, 0)) <= 0.02 THEN 1 ELSE 0 END) as balanced,
  SUM(CASE WHEN ABS(grand_total - COALESCE(p.paid_total, 0)) > 0.02 THEN 1 ELSE 0 END) as unbalanced
FROM charters c
LEFT JOIN p ON p.charter_id = c.reserve_number
WHERE grand_total > 0
""")

rule_result = cur.fetchone()
print(f"Billed charters (grand_total > 0): {rule_result['total_billed']:,}")
print(f"Balanced (zero owing): {rule_result['balanced']:,} ({100.0*rule_result['balanced']/rule_result['total_billed']:.1f}%)")
print(f"Unbalanced (outstanding): {rule_result['unbalanced']:,} ({100.0*rule_result['unbalanced']/rule_result['total_billed']:.1f}%)")

if rule_result['unbalanced'] == 0:
    print("\n✅ ALL BILLED CHARTERS ARE BALANCED TO ZERO")
else:
    print(f"\n⚠️ {rule_result['unbalanced']} charters have outstanding balances")

conn.close()
