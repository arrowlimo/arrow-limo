"""
Audit pre-2025 charters to ensure charge sums are <= total_amount_due.
Outputs:
- Counts of exact matches, overages (charge_sum > total), deficits (charge_sum < total), zero line items with total > 0.
- Samples for overages, deficits, zero line items.
- Coincidence check: zero-line-item charters that have a NULL-reserve LMS artifact matching the charter total.

Notes:
- Uses reserve_number (business key) for legitimate charge sums; excludes NULL/empty reserve_number charges from sums.
- Treats NULL/empty reserve_number charges as artifacts; they are only considered in the coincidence check.
- Read-only; no writes.
"""
import os
import psycopg2

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

CUTOFF = "2025-01-01"
print("=" * 88)
print(f"Pre-2025 charter charge parity (charter_date < {CUTOFF})")
print("=" * 88)

cur.execute("""
    SELECT COUNT(*)
    FROM charters
    WHERE charter_date < %s
""", (CUTOFF,))
(total_charters,) = cur.fetchone()
print(f"Total pre-2025 charters: {total_charters:,d}")

# Build sums by reserve_number (exclude NULL/empty)
cur.execute("""
    WITH sums AS (
        SELECT reserve_number, SUM(amount)::numeric(12,2) AS charge_sum
        FROM charter_charges
        WHERE reserve_number IS NOT NULL AND reserve_number <> ''
        GROUP BY reserve_number
    )
    SELECT
        COUNT(*) FILTER (WHERE COALESCE(s.charge_sum,0) = COALESCE(c.total_amount_due,0)) AS exact_matches,
        COUNT(*) FILTER (WHERE COALESCE(s.charge_sum,0) > COALESCE(c.total_amount_due,0)) AS overages,
        COUNT(*) FILTER (WHERE COALESCE(s.charge_sum,0) < COALESCE(c.total_amount_due,0) AND COALESCE(c.total_amount_due,0) > 0) AS deficits,
        COUNT(*) FILTER (WHERE COALESCE(s.charge_sum,0) = 0 AND COALESCE(c.total_amount_due,0) > 0) AS zero_line_items
    FROM charters c
    LEFT JOIN sums s ON s.reserve_number = c.reserve_number
    WHERE c.charter_date < %s
""", (CUTOFF,))
exact_matches, overages, deficits, zero_line_items = cur.fetchone()
print(f"Exact matches: {exact_matches:,d}")
print(f"Overages (charge_sum > total): {overages:,d}")
print(f"Deficits (charge_sum < total): {deficits:,d}")
print(f"Zero line items (total > 0): {zero_line_items:,d}")

# Samples
print("\nSample overages (limit 10):")
cur.execute("""
    WITH sums AS (
        SELECT reserve_number, SUM(amount)::numeric(12,2) AS charge_sum
        FROM charter_charges
        WHERE reserve_number IS NOT NULL AND reserve_number <> ''
        GROUP BY reserve_number
    )
    SELECT c.reserve_number, c.total_amount_due, COALESCE(s.charge_sum,0) AS charge_sum,
           (COALESCE(s.charge_sum,0) - COALESCE(c.total_amount_due,0)) AS diff, c.charter_date
    FROM charters c
    LEFT JOIN sums s ON s.reserve_number = c.reserve_number
    WHERE c.charter_date < %s AND COALESCE(s.charge_sum,0) > COALESCE(c.total_amount_due,0)
    ORDER BY diff DESC
    LIMIT 10
""", (CUTOFF,))
for reserve, total_due, charge_sum, diff, charter_date in cur.fetchall():
    print(f"  {reserve} | ${total_due:,.2f} | ${charge_sum:,.2f} | diff {diff:+,.2f} | {charter_date}")

print("\nSample deficits (limit 10):")
cur.execute("""
    WITH sums AS (
        SELECT reserve_number, SUM(amount)::numeric(12,2) AS charge_sum
        FROM charter_charges
        WHERE reserve_number IS NOT NULL AND reserve_number <> ''
        GROUP BY reserve_number
    )
    SELECT c.reserve_number, c.total_amount_due, COALESCE(s.charge_sum,0) AS charge_sum,
           (COALESCE(s.charge_sum,0) - COALESCE(c.total_amount_due,0)) AS diff, c.charter_date
    FROM charters c
    LEFT JOIN sums s ON s.reserve_number = c.reserve_number
    WHERE c.charter_date < %s AND COALESCE(s.charge_sum,0) < COALESCE(c.total_amount_due,0) AND COALESCE(c.total_amount_due,0) > 0
    ORDER BY diff ASC
    LIMIT 10
""", (CUTOFF,))
for reserve, total_due, charge_sum, diff, charter_date in cur.fetchall():
    print(f"  {reserve} | ${total_due:,.2f} | ${charge_sum:,.2f} | diff {diff:+,.2f} | {charter_date}")

print("\nSample zero line items (total > 0, limit 10):")
cur.execute("""
    WITH sums AS (
        SELECT reserve_number, SUM(amount)::numeric(12,2) AS charge_sum
        FROM charter_charges
        WHERE reserve_number IS NOT NULL AND reserve_number <> ''
        GROUP BY reserve_number
    )
    SELECT c.charter_id, c.reserve_number, c.total_amount_due, c.charter_date
    FROM charters c
    LEFT JOIN sums s ON s.reserve_number = c.reserve_number
    WHERE c.charter_date < %s AND COALESCE(c.total_amount_due,0) > 0 AND COALESCE(s.charge_sum,0) = 0
    ORDER BY c.total_amount_due DESC
    LIMIT 10
""", (CUTOFF,))
for charter_id, reserve, total_due, charter_date in cur.fetchall():
    print(f"  charter_id={charter_id} | {reserve} | ${total_due:,.2f} | {charter_date}")

# Coincidence check for zero-line-item charters
print("\nCoincidence: zero-line-item charters that have a NULL-reserve LMS artifact equal to total")
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
        WHERE c.charter_date < %s AND COALESCE(c.total_amount_due,0) > 0 AND COALESCE(s.charge_sum,0) = 0
    )
    SELECT 
        COUNT(*) FILTER (
            WHERE EXISTS (
                SELECT 1 FROM charter_charges cc
                WHERE cc.charter_id = m.charter_id
                  AND (cc.reserve_number IS NULL OR cc.reserve_number = '')
                  AND cc.description ILIKE 'Charter total (from LMS Est_Charge)%%'
                  AND cc.amount::numeric(12,2) = m.total_amount_due::numeric(12,2)
            )
        ) AS coincidences,
        COUNT(*) AS missing_total
    FROM missing m
""", (CUTOFF,))
coincidences, missing_total = cur.fetchone()
print(f"  {coincidences:,d} of {missing_total:,d} have matching LMS artifact amount")

cur.close()
conn.close()

print("\n" + "=" * 88)
print("Audit complete")
print("=" * 88)
