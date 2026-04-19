import psycopg2
from psycopg2.extras import RealDictCursor

conn = psycopg2.connect("dbname=almsdata user=postgres host=localhost password=ArrowLimousine")
cur = conn.cursor(cursor_factory=RealDictCursor)

print("=== 2012-2014 BILLED-CHARTER BALANCE CHECK ===\n")

# Get balance for 2012-2014 period
cur.execute("""
WITH p AS (
  SELECT charter_id, SUM(amount) AS paid_total
  FROM charter_payments
  GROUP BY charter_id
)
SELECT 
  EXTRACT(YEAR FROM charter_date) as year,
  COUNT(*) as total_billed,
  SUM(CASE WHEN ABS(grand_total - COALESCE(p.paid_total, 0)) <= 0.02 THEN 1 ELSE 0 END) as balanced,
  SUM(CASE WHEN ABS(grand_total - COALESCE(p.paid_total, 0)) > 0.02 THEN 1 ELSE 0 END) as unbalanced
FROM charters c
LEFT JOIN p ON p.charter_id = c.reserve_number
WHERE charter_date >= '2012-01-01' AND charter_date < '2015-01-01'
  AND grand_total > 0
GROUP BY EXTRACT(YEAR FROM charter_date)
ORDER BY year
""")

results = cur.fetchall()
total_2012_2014_billed = 0
total_2012_2014_balanced = 0
total_2012_2014_unbalanced = 0

for row in results:
    year = int(row['year'])
    total = row['total_billed']
    balanced = row['balanced']
    unbalanced = row['unbalanced']
    
    total_2012_2014_billed += total
    total_2012_2014_balanced += balanced
    total_2012_2014_unbalanced += unbalanced
    
    pct = (balanced / total * 100) if total > 0 else 0
    status = "✅ COMPLETE" if unbalanced == 0 else "❌ INCOMPLETE"
    
    print(f"{year}:")
    print(f"  Billed charters: {total}")
    print(f"  Balanced (zero owing): {balanced}")
    print(f"  Unbalanced (balance != 0): {unbalanced}")
    print(f"  Completion: {pct:.1f}% {status}")
    print()

print(f"2012-2014 TOTALS:")
print(f"  Billed charters: {total_2012_2014_billed}")
print(f"  Balanced: {total_2012_2014_balanced}")
print(f"  Unbalanced: {total_2012_2014_unbalanced}")
pct = (total_2012_2014_balanced / total_2012_2014_billed * 100) if total_2012_2014_billed > 0 else 0
if total_2012_2014_unbalanced == 0:
    print(f"\n✅ 2012-2014 IS FULLY BALANCED TO ZERO!")
else:
    print(f"\n❌ {total_2012_2014_unbalanced} charters still unbalanced in 2012-2014")

# Show any remaining unbalanced in 2012-2014
if total_2012_2014_unbalanced > 0:
    print("\n=== REMAINING UNBALANCED (2012-2014) ===\n")
    cur.execute("""
    WITH p AS (
      SELECT charter_id, SUM(amount) AS paid_total
      FROM charter_payments
      GROUP BY charter_id
    )
    SELECT 
      reserve_number,
      charter_date,
      grand_total,
      COALESCE(p.paid_total, 0) as paid,
      grand_total - COALESCE(p.paid_total, 0) as balance_owing
    FROM charters c
    LEFT JOIN p ON p.charter_id = c.reserve_number
    WHERE charter_date >= '2012-01-01' AND charter_date < '2015-01-01'
      AND grand_total > 0
      AND ABS(grand_total - COALESCE(p.paid_total, 0)) > 0.02
    ORDER BY charter_date
    LIMIT 20
    """)
    
    for row in cur.fetchall():
        print(f"{row['reserve_number']} ({row['charter_date'].date()}): " +
              f"billed ${row['grand_total']:.2f}, paid ${row['paid']:.2f}, " +
              f"owing ${row['balance_owing']:.2f}")

conn.close()
