#!/usr/bin/env python3
"""
Count ALMS charters that need correction, excluding:
- Penny-only mismatches caused by erased $0.01 LMS payments (tolerance <= $0.01)
- Quoted charters that have charges but no payment (status/booking_status contains 'quote')

Definition of "need correction": any charter where one or more holds true:
  1) total_amount_due differs from SUM(charter_charges.amount) by > $0.01
  2) paid_amount differs from SUM(payments.amount) by > $0.01
  3) balance differs from (total_amount_due - paid_amount) by > $0.01

Cancelled charters are excluded.
Read-only.
"""
import os
import psycopg2

conn = psycopg2.connect(
    host=os.getenv('DB_HOST','localhost'),
    database=os.getenv('DB_NAME','almsdata'),
    user=os.getenv('DB_USER','postgres'),
    password=os.getenv('DB_PASSWORD','***REDACTED***')
)
cur = conn.cursor()

sql = """
WITH charge_sum AS (
  SELECT reserve_number, ROUND(SUM(COALESCE(amount,0))::numeric,2) AS charges
  FROM charter_charges
  GROUP BY reserve_number
), pay_sum AS (
  SELECT reserve_number, ROUND(SUM(COALESCE(amount,0))::numeric,2) AS paid
  FROM payments
  GROUP BY reserve_number
), base AS (
  SELECT c.charter_id,
         c.reserve_number,
         COALESCE(c.total_amount_due,0)::numeric(12,2) AS total_due,
         COALESCE(cs.charges,0)::numeric(12,2)          AS charges,
         COALESCE(c.paid_amount,0)::numeric(12,2)      AS paid_field,
         COALESCE(ps.paid,0)::numeric(12,2)            AS paid_sum,
         COALESCE(c.balance, (COALESCE(c.total_amount_due,0)-COALESCE(c.paid_amount,0)))::numeric(12,2) AS balance_field,
         (COALESCE(c.total_amount_due,0) - COALESCE(c.paid_amount,0))::numeric(12,2) AS computed_balance,
         COALESCE(c.status,'') AS status,
         COALESCE(c.booking_status,'') AS booking_status,
         COALESCE(c.cancelled,false) AS cancelled
  FROM charters c
  LEFT JOIN charge_sum cs ON cs.reserve_number = c.reserve_number
  LEFT JOIN pay_sum ps    ON ps.reserve_number = c.reserve_number
)
SELECT COUNT(*)
FROM base b
WHERE cancelled = false
  AND b.status NOT ILIKE '%cancel%'
  AND b.status NOT ILIKE '%quote%'
  AND b.booking_status NOT ILIKE '%quote%'
  AND (
       ABS(b.total_due - b.charges) > 0.01
    OR ABS(b.paid_field - b.paid_sum) > 0.01
    OR ABS(b.balance_field - b.computed_balance) > 0.01
  )
"""

cur.execute(sql)
count = cur.fetchone()[0]
print("Charters needing correction (exclusions applied):", count)

cur.close(); conn.close()
