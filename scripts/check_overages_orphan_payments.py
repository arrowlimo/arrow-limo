"""
Check pre-2025 overcharged/underpaid charters against orphan payments.
- Overcharged: charge_sum > total_amount_due
- Underpaid (deficit): charge_sum < total_amount_due and total > 0
For each set, see if any orphan payment amount equals abs(diff).
Orphan payments: payments with reserve_number NULL/empty OR reserve_number not in charters.
Read-only.
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

print("="*88)
print("Pre-2025 overcharge/underpay vs orphan payments")
print("="*88)

# Build orphan payments
cur.execute("""
    CREATE TEMP TABLE orphan_payments AS
    SELECT payment_id, reserve_number, amount
    FROM payments p
    WHERE (p.reserve_number IS NULL OR p.reserve_number = '')
       OR NOT EXISTS (SELECT 1 FROM charters c WHERE c.reserve_number = p.reserve_number)
""")

# Compute diffs
cur.execute("""
    WITH sums AS (
        SELECT reserve_number, SUM(amount)::numeric(12,2) AS charge_sum
        FROM charter_charges
        WHERE reserve_number IS NOT NULL AND reserve_number <> ''
        GROUP BY reserve_number
    ), diffs AS (
        SELECT c.charter_id, c.reserve_number, c.charter_date, c.total_amount_due,
               COALESCE(s.charge_sum,0)::numeric(12,2) AS charge_sum,
               (COALESCE(s.charge_sum,0) - COALESCE(c.total_amount_due,0))::numeric(12,2) AS diff
        FROM charters c
        LEFT JOIN sums s ON s.reserve_number = c.reserve_number
        WHERE c.charter_date < %s
    )
    SELECT
        COUNT(*) FILTER (WHERE diff > 0) AS over_count,
        COUNT(*) FILTER (WHERE diff < 0 AND total_amount_due > 0) AS under_count
    FROM diffs
""", (CUTOFF,))
over_count, under_count = cur.fetchone()
print(f"Overcharged charters: {over_count:,d}")
print(f"Underpaid (deficit) charters: {under_count:,d}")

# Overcharged details with orphan payment match
print("\nOvercharged details (limit 20): reserve, total, charges, diff, has_orphan_match, sample_payment_id")
cur.execute("""
    WITH sums AS (
        SELECT reserve_number, SUM(amount)::numeric(12,2) AS charge_sum
        FROM charter_charges
        WHERE reserve_number IS NOT NULL AND reserve_number <> ''
        GROUP BY reserve_number
    ), diffs AS (
        SELECT c.charter_id, c.reserve_number, c.charter_date, c.total_amount_due,
               COALESCE(s.charge_sum,0)::numeric(12,2) AS charge_sum,
               (COALESCE(s.charge_sum,0) - COALESCE(c.total_amount_due,0))::numeric(12,2) AS diff
        FROM charters c
        LEFT JOIN sums s ON s.reserve_number = c.reserve_number
        WHERE c.charter_date < %s
    ), matches AS (
        SELECT d.charter_id,
               EXISTS (
                 SELECT 1 FROM orphan_payments op
                 WHERE op.amount::numeric(12,2) = d.diff::numeric(12,2)
               ) AS has_match,
               (SELECT op.payment_id FROM orphan_payments op WHERE op.amount::numeric(12,2) = d.diff::numeric(12,2) LIMIT 1) AS sample_payment_id
        FROM diffs d
        WHERE d.diff > 0
    )
    SELECT d.reserve_number, d.total_amount_due, d.charge_sum, d.diff,
           m.has_match, m.sample_payment_id
    FROM diffs d
    LEFT JOIN matches m ON m.charter_id = d.charter_id
    WHERE d.diff > 0
    ORDER BY d.diff DESC
    LIMIT 20
""", (CUTOFF,))
for reserve, total_due, charge_sum, diff, has_match, sample_pid in cur.fetchall():
    print(f"  {reserve} | total ${total_due:,.2f} | charges ${charge_sum:,.2f} | diff +{diff:,.2f} | orphan_match={bool(has_match)} | sample_payment_id={sample_pid}")

# Underpaid details with orphan payment match (abs(diff))
print("\nUnderpaid (deficit) details (limit 20): reserve, total, charges, diff, has_orphan_match, sample_payment_id")
cur.execute("""
    WITH sums AS (
        SELECT reserve_number, SUM(amount)::numeric(12,2) AS charge_sum
        FROM charter_charges
        WHERE reserve_number IS NOT NULL AND reserve_number <> ''
        GROUP BY reserve_number
    ), diffs AS (
        SELECT c.charter_id, c.reserve_number, c.charter_date, c.total_amount_due,
               COALESCE(s.charge_sum,0)::numeric(12,2) AS charge_sum,
               (COALESCE(s.charge_sum,0) - COALESCE(c.total_amount_due,0))::numeric(12,2) AS diff
        FROM charters c
        LEFT JOIN sums s ON s.reserve_number = c.reserve_number
        WHERE c.charter_date < %s AND COALESCE(c.total_amount_due,0) > 0
    ), matches AS (
        SELECT d.charter_id,
               EXISTS (
                 SELECT 1 FROM orphan_payments op
                 WHERE op.amount::numeric(12,2) = ABS(d.diff)::numeric(12,2)
               ) AS has_match,
               (SELECT op.payment_id FROM orphan_payments op WHERE op.amount::numeric(12,2) = ABS(d.diff)::numeric(12,2) LIMIT 1) AS sample_payment_id
        FROM diffs d
        WHERE d.diff < 0
    )
    SELECT d.reserve_number, d.total_amount_due, d.charge_sum, d.diff,
           m.has_match, m.sample_payment_id
    FROM diffs d
    LEFT JOIN matches m ON m.charter_id = d.charter_id
    WHERE d.diff < 0
    ORDER BY d.diff ASC
    LIMIT 20
""", (CUTOFF,))
for reserve, total_due, charge_sum, diff, has_match, sample_pid in cur.fetchall():
    print(f"  {reserve} | total ${total_due:,.2f} | charges ${charge_sum:,.2f} | diff {diff:,.2f} | orphan_match={bool(has_match)} | sample_payment_id={sample_pid}")

# Aggregate how many over/under have orphan matches
print("\nAggregate match counts:")
cur.execute("""
    WITH sums AS (
        SELECT reserve_number, SUM(amount)::numeric(12,2) AS charge_sum
        FROM charter_charges
        WHERE reserve_number IS NOT NULL AND reserve_number <> ''
        GROUP BY reserve_number
    ), diffs AS (
        SELECT c.charter_id, c.reserve_number, c.charter_date, c.total_amount_due,
               COALESCE(s.charge_sum,0)::numeric(12,2) AS charge_sum,
               (COALESCE(s.charge_sum,0) - COALESCE(c.total_amount_due,0))::numeric(12,2) AS diff
        FROM charters c
        LEFT JOIN sums s ON s.reserve_number = c.reserve_number
        WHERE c.charter_date < %s
    )
    SELECT
        COUNT(*) FILTER (
            WHERE diff > 0 AND EXISTS (SELECT 1 FROM orphan_payments op WHERE op.amount::numeric(12,2) = diff::numeric(12,2))
        ) AS over_with_orphan,
        COUNT(*) FILTER (
            WHERE diff > 0
        ) AS over_total,
        COUNT(*) FILTER (
            WHERE diff < 0 AND total_amount_due > 0 AND EXISTS (SELECT 1 FROM orphan_payments op WHERE op.amount::numeric(12,2) = ABS(diff)::numeric(12,2))
        ) AS under_with_orphan,
        COUNT(*) FILTER (
            WHERE diff < 0 AND total_amount_due > 0
        ) AS under_total
    FROM diffs
""", (CUTOFF,))
over_with_orphan, over_total, under_with_orphan, under_total = cur.fetchone()
print(f"  Overcharged with orphan payment match: {over_with_orphan} of {over_total}")
print(f"  Underpaid with orphan payment match:   {under_with_orphan} of {under_total}")

conn.close()

print("\n" + "="*88)
print("Check complete")
print("="*88)
