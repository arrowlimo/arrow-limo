import psycopg2
import os

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

reserve = "018841"

# First get the charter_id
cur.execute("SELECT charter_id FROM charters WHERE reserve_number = %s", (reserve,))
result = cur.fetchone()
if not result:
    print(f"Charter {reserve} not found")
    cur.close()
    conn.close()
    exit(1)

charter_id = result[0]

# Update the NULL reserve_number charge
cur.execute("""
    UPDATE charter_charges
    SET reserve_number = %s
    WHERE charter_id = %s
    AND reserve_number IS NULL
    AND description LIKE '%LMS%'
""", (reserve, charter_id))

updated = cur.rowcount
conn.commit()

print(f"✅ Updated {updated} LMS artifact(s) to link reserve_number = {reserve}")

# Verify
cur.execute("""
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
        COUNT(*) AS total_charters
    FROM charters c
    LEFT JOIN sums s ON c.reserve_number = s.reserve_number
    WHERE c.charter_date < '2025-01-01'
""")

row = cur.fetchone()
print(f"\nFinal Pre-2025 Audit (after 018841 fix):")
print(f"  Exact matches: {row[0]:,}")
print(f"  Overages:      {row[1]}")
print(f"  Deficits:      {row[2]}")
print(f"  Total charters: {row[3]:,}")

if row[2] == 0:
    print(f"\n🎉 ALL PRE-2025 DEFICITS RESOLVED!")

cur.close()
conn.close()
