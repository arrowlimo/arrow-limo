import psycopg2
import os

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

sql = """
WITH sums AS (
    SELECT reserve_number, SUM(amount) AS charge_sum
    FROM charter_charges
    WHERE reserve_number IS NOT NULL
    GROUP BY reserve_number
)
SELECT c.reserve_number, c.status, c.total_amount_due, s.charge_sum, 
       (c.total_amount_due - s.charge_sum) AS diff
FROM charters c
LEFT JOIN sums s ON c.reserve_number = s.reserve_number
WHERE c.charter_date < '2025-01-01'
  AND c.total_amount_due > 0
  AND s.charge_sum < c.total_amount_due
ORDER BY diff ASC
LIMIT 80;
"""

cur.execute(sql)
rows = cur.fetchall()

with open('L:\\limo\\reports\\deficit_list_top80.txt', 'w') as f:
    f.write(f"{'Reserve':<10} {'Status':<12} {'Total':>12} {'Charges':>12} {'Deficit':>12}\n")
    f.write("=" * 60 + "\n")
    for row in rows:
        f.write(f"{row[0]:<10} {row[1] or 'NULL':<12} {row[2]:>12.2f} {row[3]:>12.2f} {row[4]:>12.2f}\n")

print(f"✅ Written {len(rows)} deficit charters to reports/deficit_list_top80.txt")
cur.close()
conn.close()
