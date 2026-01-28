import psycopg2
import os

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

# Get overages
sql = """
    WITH sums AS (
        SELECT reserve_number, SUM(amount) AS charge_sum
        FROM charter_charges
        WHERE reserve_number IS NOT NULL
        GROUP BY reserve_number
    )
    SELECT c.reserve_number, c.status, c.charter_date, c.total_amount_due, s.charge_sum,
           (s.charge_sum - c.total_amount_due) AS overage,
           COALESCE(p.pay_sum, 0) as paid
    FROM charters c
    LEFT JOIN sums s ON c.reserve_number = s.reserve_number
    LEFT JOIN (SELECT reserve_number, SUM(amount) as pay_sum FROM payments GROUP BY reserve_number) p 
        ON c.reserve_number = p.reserve_number
    WHERE c.charter_date < '2025-01-01'
    AND c.total_amount_due > 0
    AND s.charge_sum > c.total_amount_due
    ORDER BY overage DESC
"""

cur.execute(sql)
rows = cur.fetchall()

print(f"{'='*80}")
print(f"PRE-2025 CHARTERS WITH OVERAGES (charges > total_amount_due)")
print(f"{'='*80}\n")
print(f"{'Reserve':<10} {'Status':<12} {'Total':>12} {'Charges':>12} {'Overage':>12} {'Paid':>12}")
print(f"{'-'*80}")

for row in rows:
    print(f"{row[0]:<10} {(row[1] or 'NULL'):<12} ${row[3]:>11.2f} ${row[4]:>11.2f} ${row[5]:>11.2f} ${row[6]:>11.2f}")

print(f"\nTotal overages: {len(rows)}")

# Check if any are paid in full
paid_in_full = sum(1 for r in rows if r[6] >= r[3])
print(f"Paid in full (can be explained by overage): {paid_in_full}")

cur.close()
conn.close()
