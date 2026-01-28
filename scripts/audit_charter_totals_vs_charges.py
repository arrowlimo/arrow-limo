"""
Audit: Do charters' totals equal the sum of their line-item charges?
Additionally: For charters with totals but zero linked line items, check whether
there exists a NULL-reserve 'Charter total (from LMS Est_Charge)...' artifact
for the same charter_id with amount equal to the charter's total.

Rules:
- Use reserve_number as the business key for summing legitimate charges.
- Treat NULL/empty reserve_number charter_charges as artifacts (exclude from sums).
- Read-only: no writes.
"""
import os
import psycopg2

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

print("="*88)
print("Charter totals vs charge line-item sums (business key: reserve_number)")
print("="*88)

# Total charters
cur.execute("SELECT COUNT(*) FROM charters")
(total_charters,) = cur.fetchone()
print(f"Total charters: {total_charters:,d}")

# Summed charges by reserve_number (exclude NULL/empty reserve_number)
cur.execute("""
    WITH sums AS (
        SELECT reserve_number, SUM(amount)::numeric(12,2) AS charge_sum
        FROM charter_charges
        WHERE reserve_number IS NOT NULL AND reserve_number <> ''
        GROUP BY reserve_number
    )
    SELECT
        COUNT(*) FILTER (WHERE COALESCE(s.charge_sum,0) = COALESCE(c.total_amount_due,0)) AS exact_matches,
        COUNT(*) FILTER (WHERE COALESCE(s.charge_sum,0) <> COALESCE(c.total_amount_due,0)) AS mismatches,
        COUNT(*) FILTER (WHERE s.reserve_number IS NULL) AS no_line_items
    FROM charters c
    LEFT JOIN sums s ON s.reserve_number = c.reserve_number
""")
exact_matches, mismatches, no_line_items = cur.fetchone()
print(f"Exact matches: {exact_matches:,d}")
print(f"Mismatches:    {mismatches:,d}")
print(f"No line items:  {no_line_items:,d}")

# Detail: list sample mismatches
print("\nSample mismatches (limit 10): reserve, total_amount_due, charge_sum, diff")
cur.execute("""
    WITH sums AS (
        SELECT reserve_number, SUM(amount)::numeric(12,2) AS charge_sum
        FROM charter_charges
        WHERE reserve_number IS NOT NULL AND reserve_number <> ''
        GROUP BY reserve_number
    )
    SELECT c.reserve_number, c.total_amount_due, COALESCE(s.charge_sum,0) AS charge_sum,
           (COALESCE(s.charge_sum,0) - COALESCE(c.total_amount_due,0)) AS diff
    FROM charters c
    LEFT JOIN sums s ON s.reserve_number = c.reserve_number
    WHERE COALESCE(s.charge_sum,0) <> COALESCE(c.total_amount_due,0)
    ORDER BY ABS(COALESCE(s.charge_sum,0) - COALESCE(c.total_amount_due,0)) DESC
    LIMIT 10
""")
rows = cur.fetchall()
for r in rows:
    reserve, total_due, charge_sum, diff = r
    print(f"  {reserve} | ${total_due:,.2f} | ${charge_sum:,.2f} | {diff:+,.2f}")

# Charters with totals but zero line items
print("\nCharters with totals > 0 but zero line items (count + sample)")
cur.execute("""
    WITH sums AS (
        SELECT reserve_number, SUM(amount)::numeric(12,2) AS charge_sum
        FROM charter_charges
        WHERE reserve_number IS NOT NULL AND reserve_number <> ''
        GROUP BY reserve_number
    )
    SELECT COUNT(*)
    FROM charters c
    LEFT JOIN sums s ON s.reserve_number = c.reserve_number
    WHERE COALESCE(c.total_amount_due,0) > 0 AND COALESCE(s.charge_sum,0) = 0
""")
(missing_count,) = cur.fetchone()
print(f"  Count: {missing_count:,d}")

cur.execute("""
    WITH sums AS (
        SELECT reserve_number, SUM(amount)::numeric(12,2) AS charge_sum
        FROM charter_charges
        WHERE reserve_number IS NOT NULL AND reserve_number <> ''
        GROUP BY reserve_number
    )
    SELECT c.charter_id, c.reserve_number, c.total_amount_due
    FROM charters c
    LEFT JOIN sums s ON s.reserve_number = c.reserve_number
    WHERE COALESCE(c.total_amount_due,0) > 0 AND COALESCE(s.charge_sum,0) = 0
    ORDER BY c.total_amount_due DESC
    LIMIT 10
""")
rows = cur.fetchall()
for charter_id, reserve, total_due in rows:
    print(f"  charter_id={charter_id} | {reserve} | ${total_due:,.2f}")

# Coincidence check: do missing-line-item charters have a NULL-reserve LMS total artifact equal to total?
print("\nCoincidence check: artifacts equal to charter total among missing-line-item charters")
cur.execute("""
    WITH sums AS (
        SELECT reserve_number, SUM(amount)::numeric(12,2) AS charge_sum
        FROM charter_charges
        WHERE reserve_number IS NOT NULL AND reserve_number <> ''
        GROUP BY reserve_number
    ), missing AS (
        SELECT c.charter_id, c.reserve_number, c.total_amount_due
        FROM charters c
        LEFT JOIN sums s ON s.reserve_number = c.reserve_number
        WHERE COALESCE(c.total_amount_due,0) > 0 AND COALESCE(s.charge_sum,0) = 0
    )
    SELECT 
        COUNT(*) FILTER (
            WHERE EXISTS (
                SELECT 1 FROM charter_charges cc
                WHERE cc.charter_id = m.charter_id
                  AND (cc.reserve_number IS NULL OR cc.reserve_number = '')
                  AND cc.description ILIKE 'Charter total (from LMS Est_Charge)%'
                  AND cc.amount::numeric(12,2) = m.total_amount_due::numeric(12,2)
            )
        ) AS coincidences,
        COUNT(*) AS missing_total
    FROM missing m
""")
coincidences, missing_total = cur.fetchone()
print(f"  Missing-line-item charters with matching artifact = total: {coincidences:,d} of {missing_total:,d}")

cur.close()
conn.close()

print("\n"+"="*88)
print("Audit complete")
print("="*88)
