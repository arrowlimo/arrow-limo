import psycopg2
from psycopg2.extras import RealDictCursor
from decimal import Decimal

conn = psycopg2.connect("dbname=almsdata user=postgres host=localhost password=ArrowLimousine")
cur = conn.cursor(cursor_factory=RealDictCursor)

print("=== CHARTER REVENUE & PAYMENT RECONCILIATION ===\n")

# Get by year
cur.execute("""
WITH p AS (
  SELECT charter_id, SUM(amount) AS paid_total
  FROM charter_payments
  GROUP BY charter_id
),
yearly AS (
  SELECT 
    EXTRACT(YEAR FROM charter_date) as year,
    COUNT(*) as charter_count,
    SUM(grand_total) as invoiced_total,
    COALESCE(SUM(p.paid_total), 0) as payments_total,
    SUM(grand_total) - COALESCE(SUM(p.paid_total), 0) as difference
  FROM charters c
  LEFT JOIN p ON p.charter_id = c.reserve_number
  WHERE grand_total > 0
  GROUP BY EXTRACT(YEAR FROM charter_date)
  ORDER BY year
)
SELECT 
  year,
  charter_count,
  invoiced_total,
  payments_total,
  difference,
  ROUND(100.0 * payments_total / NULLIF(invoiced_total, 0), 1) as collection_pct
FROM yearly
""")

results = cur.fetchall()

total_invoiced = Decimal('0')
total_paid = Decimal('0')
total_difference = Decimal('0')

print("Year | Charters | Invoiced Total | Payments Total | Difference | Collection %")
print("-----|----------|----------------|----------------|------------|-------------")

for row in results:
    year = int(row['year'])
    count = row['charter_count']
    invoiced = row['invoiced_total']
    paid = row['payments_total']
    diff = row['difference']
    pct = row['collection_pct'] if row['collection_pct'] is not None else 0
    
    total_invoiced += Decimal(str(invoiced)) if invoiced else Decimal('0')
    total_paid += Decimal(str(paid)) if paid else Decimal('0')
    total_difference += Decimal(str(diff)) if diff else Decimal('0')
    
    print(f"{year} | {count:8} | ${invoiced:13,.2f} | ${paid:13,.2f} | ${diff:10,.2f} | {pct:6.1f}%")

print("-----|----------|----------------|----------------|------------|-------------")
collection_pct = float(total_paid) / float(total_invoiced) * 100.0 if total_invoiced > 0 else 0
print(f"TOTAL| {'':<8} | ${float(total_invoiced):13,.2f} | ${float(total_paid):13,.2f} | ${float(total_difference):10,.2f} | {collection_pct:6.1f}%")

print("\n=== SUMMARY ===")
print(f"Total Charter Invoicing (grand_total): ${float(total_invoiced):,.2f}")
print(f"Total Payments Received: ${float(total_paid):,.2f}")
print(f"Unmatched/Outstanding: ${float(total_difference):,.2f}")
print(f"Collection Rate: {collection_pct:.1f}%")

# Show balance by payment source
print("\n=== PAYMENT BREAKDOWN BY SOURCE ===\n")
cur.execute("""
SELECT 
  source,
  COUNT(*) as payment_count,
  SUM(amount) as total_amount
FROM charter_payments
GROUP BY source
ORDER BY total_amount DESC
""")

for row in cur.fetchall():
    print(f"{row['source']:<30} {row['payment_count']:>6} payments  ${row['total_amount']:>13,.2f}")

# Check for zero-billed charters with payments (should be none now)
print("\n=== DATA QUALITY CHECK ===\n")
cur.execute("""
SELECT COUNT(*) as abnormal_count
FROM charters c
WHERE grand_total = 0
  AND EXISTS (
    SELECT 1 FROM charter_payments cp WHERE cp.charter_id = c.reserve_number
  )
""")

abnormal = cur.fetchone()['abnormal_count']
print(f"Zero-billed charters with payments: {abnormal}")
if abnormal == 0:
    print("  ✅ PASS - No data anomalies found")
else:
    print(f"  ❌ FAIL - {abnormal} anomalies detected")

# Check for non-zero balances on pre-2015 charters
print("\n=== PRE-2015 BALANCE SUMMARY ===\n")
cur.execute("""
WITH p AS (
  SELECT charter_id, SUM(amount) AS paid_total
  FROM charter_payments
  GROUP BY charter_id
),
status_check AS (
  SELECT 
    CASE 
      WHEN ABS(COALESCE(c.grand_total, 0) - COALESCE(p.paid_total, 0)) <= 0.02 THEN 'Balanced'
      ELSE 'Unbalanced'
    END as status,
    COUNT(*) as charter_count,
    SUM(COALESCE(c.grand_total, 0) - COALESCE(p.paid_total, 0)) as total_difference
  FROM charters c
  LEFT JOIN p ON p.charter_id = c.reserve_number
  WHERE c.charter_date < '2015-01-01'
    AND c.grand_total > 0
  GROUP BY 1
)
SELECT * FROM status_check
""")

for row in cur.fetchall():
    print(f"{row['status']:<15} {row['charter_count']:>6} charters, Difference: ${row['total_difference']:>13,.2f}")

conn.close()
