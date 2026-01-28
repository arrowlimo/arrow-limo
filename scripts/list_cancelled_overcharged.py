"""
List overcharged pre-2025 charters ordered by diff desc (excluding 017364). Shows status so we can decide which to fix next.
"""
import os
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
        WHERE reserve_number IS NOT NULL AND reserve_number<>''
        GROUP BY reserve_number
    )
    SELECT c.reserve_number, c.status, c.total_amount_due, COALESCE(s.charge_sum,0) AS charge_sum,
           (COALESCE(s.charge_sum,0)-COALESCE(c.total_amount_due,0)) AS diff
    FROM charters c
    LEFT JOIN sums s ON s.reserve_number=c.reserve_number
    WHERE c.charter_date < %s AND (COALESCE(s.charge_sum,0) > COALESCE(c.total_amount_due,0))
    ORDER BY diff DESC
    """,
    (CUTOFF,),
)
rows = cur.fetchall()
cur.close()
conn.close()

targets = []
for r in rows:
    res, status, tot, cs, diff = r
    if res == "017364":
        continue
    if status and status.lower().startswith("cancel"):
        targets.append(r)

    # Top 10 overcharged overall (exclude 017364)
    print("Overcharged (exclude 017364), top 10:")
    for r in [row for row in rows if row[0] != "017364"][:10]:
        res, status, tot, cs, diff = r
        print(f"  {res} | status={status} | total={tot} | charges={cs} | diff=+{diff}")
