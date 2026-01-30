#!/usr/bin/env python3
"""
Check both reserve_number and charter_id linkage for payment mismatches.
"""
import os, psycopg2

conn = psycopg2.connect(
    host=os.getenv('DB_HOST','localhost'),
    database=os.getenv('DB_NAME','almsdata'),
    user=os.getenv('DB_USER','postgres'),
    password=os.getenv('DB_PASSWORD','***REDACTED***')
)
cur = conn.cursor()

print("=" * 80)
print("PAYMENT LINKAGE ANALYSIS")
print("=" * 80)

# Check via reserve_number
cur.execute("""
    WITH pay_sum AS (
        SELECT reserve_number, 
               ROUND(SUM(COALESCE(amount,0))::numeric,2) AS actual_paid
        FROM payments
        WHERE reserve_number IS NOT NULL
        GROUP BY reserve_number
    )
    SELECT COUNT(*)
    FROM charters c
    INNER JOIN pay_sum ps ON ps.reserve_number = c.reserve_number
    WHERE COALESCE(c.cancelled, FALSE) = FALSE
      AND ABS(COALESCE(c.paid_amount,0) - ps.actual_paid) > 0.01
""")
reserve_count = cur.fetchone()[0]
print(f"Mismatches via reserve_number linkage: {reserve_count}")

# Check via charter_id
cur.execute("""
    WITH pay_sum AS (
        SELECT charter_id, 
               ROUND(SUM(COALESCE(amount,0))::numeric,2) AS actual_paid
        FROM payments
        WHERE reserve_number IS NOT NULL
        GROUP BY charter_id
    )
    SELECT COUNT(*)
    FROM charters c
    INNER JOIN pay_sum ps ON ps.charter_id = c.charter_id
    WHERE COALESCE(c.cancelled, FALSE) = FALSE
      AND ABS(COALESCE(c.paid_amount,0) - ps.actual_paid) > 0.01
""")
charter_id_count = cur.fetchone()[0]
print(f"Mismatches via charter_id linkage: {charter_id_count}")

# Get samples from reserve_number mismatches
print("\nTop 10 via reserve_number:")
cur.execute("""
    WITH pay_sum AS (
        SELECT reserve_number, 
               ROUND(SUM(COALESCE(amount,0))::numeric,2) AS actual_paid
        FROM payments
        WHERE reserve_number IS NOT NULL
        GROUP BY reserve_number
    )
    SELECT c.reserve_number, c.charter_id,
           c.paid_amount, ps.actual_paid,
           ABS(COALESCE(c.paid_amount,0) - ps.actual_paid) as diff
    FROM charters c
    INNER JOIN pay_sum ps ON ps.reserve_number = c.reserve_number
    WHERE COALESCE(c.cancelled, FALSE) = FALSE
      AND ABS(COALESCE(c.paid_amount,0) - ps.actual_paid) > 0.01
    ORDER BY diff DESC
    LIMIT 10
""")
for row in cur.fetchall():
    print(f"  {row[0]}: paid_amount=${row[2] or 0:.2f}, SUM(payments)=${row[3]:.2f}, diff=${row[4]:.2f}")

cur.close()
conn.close()
