import os, psycopg2
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))
CUTOFF = "2025-01-01"
conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()
cur.execute("""
    WITH sums AS (
        SELECT reserve_number, SUM(amount)::numeric(12,2) AS charge_sum
        FROM charter_charges
        WHERE reserve_number IS NOT NULL AND reserve_number <> ''
        GROUP BY reserve_number
    )
    SELECT c.reserve_number, c.status, c.total_amount_due, COALESCE(s.charge_sum,0) AS charge_sum,
           (COALESCE(s.charge_sum,0) - COALESCE(c.total_amount_due,0)) AS diff
    FROM charters c
    LEFT JOIN sums s ON s.reserve_number = c.reserve_number
    WHERE c.charter_date < %s AND COALESCE(s.charge_sum,0) < COALESCE(c.total_amount_due,0) AND COALESCE(c.total_amount_due,0) > 0
    ORDER BY diff ASC
""", (CUTOFF,))
rows = cur.fetchall()
cur.close(); conn.close()
with open('reports/deficit_list_top80.txt', 'w') as f:
    f.write(f"Total deficits (charge_sum < total): {len(rows)}\n")
    f.write("\nTop 80 (most missing charges):\n")
    f.write("reserve | status | total | charges | diff\n")
    for r in rows[:80]:
        res,status,tot,cs,diff=r
        f.write(f"{res} | {status or 'NULL':15s} | ${tot:8,.2f} | ${cs:8,.2f} | {diff:+9,.2f}\n")
print('Written to reports/deficit_list_top80.txt')
