#!/usr/bin/env python3
"""
Count charters needing correction excluding:
1. $0.01 penny payments erased from LMS (tolerance)
2. Quoted charters with charges but no payment

Focus on real discrepancies where paid_amount != SUM(payments.amount)
"""
import os, psycopg2

conn = psycopg2.connect(
    host=os.getenv('DB_HOST','localhost'),
    database=os.getenv('DB_NAME','almsdata'),
    user=os.getenv('DB_USER','postgres'),
    password=os.getenv('DB_PASSWORD','***REMOVED***')
)
cur = conn.cursor()

# Count charters where paid_amount doesn't match actual payment sum
# excluding quotes and cancelled
cur.execute("""
    WITH pay_sum AS (
        SELECT reserve_number, 
               ROUND(SUM(COALESCE(amount,0))::numeric,2) AS actual_paid
        FROM payments
        GROUP BY reserve_number
    )
    SELECT COUNT(*)
    FROM charters c
    LEFT JOIN pay_sum ps ON ps.reserve_number = c.reserve_number
    WHERE COALESCE(c.cancelled, FALSE) = FALSE
      AND COALESCE(c.status, '') NOT ILIKE '%cancel%'
      AND COALESCE(c.status, '') NOT ILIKE '%quote%'
      AND COALESCE(c.booking_status, '') NOT ILIKE '%quote%'
      AND ABS(COALESCE(c.paid_amount,0) - COALESCE(ps.actual_paid,0)) > 0.01
""")

count = cur.fetchone()[0]
print(f"Charters needing correction: {count}")

# Get sample details
cur.execute("""
    WITH pay_sum AS (
        SELECT reserve_number, 
               ROUND(SUM(COALESCE(amount,0))::numeric,2) AS actual_paid
        FROM payments
        GROUP BY reserve_number
    )
    SELECT c.reserve_number, 
           c.charter_id,
           c.paid_amount as charter_paid,
           ps.actual_paid as sum_payments,
           ABS(COALESCE(c.paid_amount,0) - COALESCE(ps.actual_paid,0)) as diff
    FROM charters c
    LEFT JOIN pay_sum ps ON ps.reserve_number = c.reserve_number
    WHERE COALESCE(c.cancelled, FALSE) = FALSE
      AND COALESCE(c.status, '') NOT ILIKE '%cancel%'
      AND COALESCE(c.status, '') NOT ILIKE '%quote%'
      AND COALESCE(c.booking_status, '') NOT ILIKE '%quote%'
      AND ABS(COALESCE(c.paid_amount,0) - COALESCE(ps.actual_paid,0)) > 0.01
    ORDER BY diff DESC
    LIMIT 10
""")

print("\nTop 10 discrepancies:")
for reserve, charter_id, charter_paid, sum_pay, diff in cur.fetchall():
    print(f"  {reserve}: charter.paid=${charter_paid or 0:.2f}, SUM(payments)=${sum_pay or 0:.2f}, diff=${diff:.2f}")

cur.close()
conn.close()
