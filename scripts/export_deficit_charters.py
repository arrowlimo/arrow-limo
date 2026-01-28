"""
Export pre-2025 charters where charge_sum < total_amount_due (total>0) to CSV for manual remediation.
Outputs: reports/charter_deficits_pre2025.csv
Columns: reserve_number, status, charter_date, total_amount_due, charge_sum, diff, payments_sum, payment_count
"""
import os
import csv
import psycopg2

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")
CUTOFF = "2025-01-01"

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

cur.execute(
    """
    WITH sums AS (
        SELECT reserve_number, SUM(amount)::numeric(12,2) AS charge_sum
        FROM charter_charges
        WHERE reserve_number IS NOT NULL AND reserve_number <> ''
        GROUP BY reserve_number
    ), pays AS (
        SELECT reserve_number, COUNT(*) AS pay_count, SUM(amount)::numeric(12,2) AS pay_sum
        FROM payments
        GROUP BY reserve_number
    )
    SELECT c.reserve_number,
           c.status,
           c.charter_date,
           c.total_amount_due::numeric(12,2),
           COALESCE(s.charge_sum,0)::numeric(12,2) AS charge_sum,
           (COALESCE(s.charge_sum,0) - COALESCE(c.total_amount_due,0))::numeric(12,2) AS diff,
           COALESCE(p.pay_sum,0)::numeric(12,2) AS payments_sum,
           COALESCE(p.pay_count,0) AS payment_count
    FROM charters c
    LEFT JOIN sums s ON s.reserve_number = c.reserve_number
    LEFT JOIN pays p ON p.reserve_number = c.reserve_number
    WHERE c.charter_date < %s
      AND COALESCE(c.total_amount_due,0) > 0
      AND COALESCE(s.charge_sum,0) < COALESCE(c.total_amount_due,0)
    ORDER BY diff ASC
    """,
    (CUTOFF,),
)
rows = cur.fetchall()
cur.close(); conn.close()

os.makedirs("reports", exist_ok=True)
out_path = "reports/charter_deficits_pre2025.csv"
with open(out_path, "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow([
        "reserve_number",
        "status",
        "charter_date",
        "total_amount_due",
        "charge_sum",
        "diff",
        "payments_sum",
        "payment_count",
    ])
    w.writerows(rows)

print(f"Exported {len(rows)} deficit charters to {out_path}")
print("Top 5 preview:")
for r in rows[:5]:
    print(r)
