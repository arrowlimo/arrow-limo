#!/usr/bin/env python
"""Quick check of problem charters with corrected join."""
import psycopg2

conn = psycopg2.connect('host=localhost dbname=almsdata user=postgres password=***REDACTED***')
cur = conn.cursor()

cur.execute("""
WITH cp_sums AS (
  SELECT 
    charter_id AS reserve_num,
    SUM(amount) AS cp_total,
    COUNT(*) AS cp_count
  FROM charter_payments
  WHERE charter_id IS NOT NULL
  GROUP BY charter_id
)
SELECT 
  c.charter_id,
  c.reserve_number,
  c.paid_amount,
  cp.cp_total,
  cp.cp_count,
  ABS(c.paid_amount - cp.cp_total) AS diff
FROM charters c
JOIN cp_sums cp ON cp.reserve_num = c.reserve_number
WHERE c.charter_id IN (16187, 17555, 16948)
ORDER BY c.charter_id
""")

print("Charter | Reserve | paid_amount | charter_payments | #Pay | Difference")
print("-" * 75)
for row in cur.fetchall():
    cid, reserve, paid, cp_total, count, diff = row
    match_indicator = "✓ MATCH" if diff < 0.02 else "✗ MISMATCH"
    print(f"{cid:7d} | {reserve:7s} | ${paid:10,.2f} | ${cp_total:15,.2f} | {count:4d} | ${diff:8,.2f} {match_indicator}")

cur.close()
conn.close()
