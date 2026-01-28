import psycopg2
import os

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

# Count exact match, overages, deficits for pre-2025
sql = """
WITH sums AS (
    SELECT reserve_number, SUM(amount) AS charge_sum
    FROM charter_charges
    WHERE reserve_number IS NOT NULL
    GROUP BY reserve_number
)
SELECT 
    COUNT(CASE WHEN c.total_amount_due = s.charge_sum THEN 1 END) AS exact_match,
    COUNT(CASE WHEN c.total_amount_due < s.charge_sum THEN 1 END) AS overages,
    COUNT(CASE WHEN c.total_amount_due > 0 AND s.charge_sum < c.total_amount_due THEN 1 END) AS deficits,
    COUNT(CASE WHEN s.charge_sum IS NULL OR s.charge_sum = 0 THEN 1 END) AS zero_charges,
    COUNT(*) AS total_charters
FROM charters c
LEFT JOIN sums s ON c.reserve_number = s.reserve_number
WHERE c.charter_date < '2025-01-01';
"""

cur.execute(sql)
row = cur.fetchone()

print(f"Pre-2025 Charter Charge Parity Audit:")
print(f"  Total charters:  {row[4]}")
print(f"  Exact matches:   {row[0]}")
print(f"  Overages:        {row[1]} (charges > total)")
print(f"  Deficits:        {row[2]} (charges < total, total > 0)")
print(f"  Zero charges:    {row[3]}")
print(f"\n342 vs {row[2]} - need to investigate discrepancy")

cur.close()
conn.close()
