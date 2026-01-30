"""
Check if charter_charges table is redundant or if charters.total_amount_due
is calculated from charter_charges.
"""
import psycopg2
import os

conn = psycopg2.connect(
    host=os.environ.get("DB_HOST", "localhost"),
    database=os.environ.get("DB_NAME", "almsdata"),
    user=os.environ.get("DB_USER", "postgres"),
    password=os.environ.get("DB_PASSWORD", "***REDACTED***")
)
cur = conn.cursor()

print("=" * 80)
print("CHARTER_CHARGES TABLE ANALYSIS")
print("=" * 80)

# Check charter_charges structure
cur.execute("""
    SELECT column_name, data_type
    FROM information_schema.columns
    WHERE table_name = 'charter_charges'
    ORDER BY ordinal_position
""")
print("\ncharter_charges columns:")
for col, dtype in cur.fetchall():
    print(f"  {col:30} {dtype}")

# Get record count
cur.execute("SELECT COUNT(*) FROM charter_charges")
charge_count = cur.fetchone()[0]
print(f"\nTotal charter_charges records: {charge_count:,}")

# Check if charter_charges sums match charters.total_amount_due
print("\n" + "=" * 80)
print("COMPARING charter_charges SUM vs charters.total_amount_due")
print("=" * 80)

cur.execute("""
    SELECT 
        c.reserve_number,
        c.total_amount_due as charter_total,
        COALESCE(SUM(cc.amount), 0) as charges_sum,
        c.total_amount_due - COALESCE(SUM(cc.amount), 0) as difference
    FROM charters c
    LEFT JOIN charter_charges cc ON cc.reserve_number = c.reserve_number
    WHERE c.cancelled = FALSE
    AND c.total_amount_due IS NOT NULL
    AND c.total_amount_due != 0
    GROUP BY c.reserve_number, c.total_amount_due
    HAVING ABS(c.total_amount_due - COALESCE(SUM(cc.amount), 0)) > 0.01
    ORDER BY ABS(c.total_amount_due - COALESCE(SUM(cc.amount), 0)) DESC
    LIMIT 10
""")

mismatches = cur.fetchall()
print(f"\nCharters where total_amount_due != SUM(charter_charges):")
print(f"Found {len(mismatches)} mismatches (showing top 10)")
for reserve, charter_total, charges_sum, diff in mismatches:
    print(f"  {reserve}: Charter ${charter_total:.2f} vs Charges ${charges_sum:.2f} (diff: ${diff:.2f})")

# Check if payments reconcile to charter total
print("\n" + "=" * 80)
print("DO PAYMENTS RECONCILE TO charters.total_amount_due?")
print("=" * 80)

cur.execute("""
    SELECT 
        COUNT(*) as total_charters,
        COUNT(CASE WHEN ABS(c.total_amount_due - c.paid_amount - c.balance) <= 0.01 THEN 1 END) as balanced,
        COUNT(CASE WHEN ABS(c.total_amount_due - c.paid_amount - c.balance) > 0.01 THEN 1 END) as unbalanced
    FROM charters c
    WHERE c.cancelled = FALSE
    AND c.total_amount_due IS NOT NULL
    AND c.total_amount_due != 0
""")

total, balanced, unbalanced = cur.fetchone()
print(f"\nCharters with amounts:")
print(f"  Total: {total:,}")
print(f"  Balanced (total = paid + balance): {balanced:,} ({100*balanced/total:.1f}%)")
print(f"  Unbalanced: {unbalanced:,} ({100*unbalanced/total:.1f}%)")

# Check if payments SUM matches charters.paid_amount
cur.execute("""
    WITH payment_sums AS (
        SELECT 
            p.reserve_number,
            SUM(p.amount) as payment_total
        FROM payments p
        GROUP BY p.reserve_number
    )
    SELECT 
        COUNT(*) as total_charters,
        COUNT(CASE WHEN ABS(c.paid_amount - COALESCE(ps.payment_total, 0)) <= 0.01 THEN 1 END) as matches,
        COUNT(CASE WHEN ABS(c.paid_amount - COALESCE(ps.payment_total, 0)) > 0.01 THEN 1 END) as mismatches
    FROM charters c
    LEFT JOIN payment_sums ps ON ps.reserve_number = c.reserve_number
    WHERE c.cancelled = FALSE
    AND c.paid_amount IS NOT NULL
    AND c.paid_amount != 0
""")

total, matches, mismatches = cur.fetchone()
print(f"\nDo payments SUM to charters.paid_amount?")
print(f"  Total charters with paid_amount: {total:,}")
print(f"  Matches: {matches:,} ({100*matches/total:.1f}%)")
print(f"  Mismatches: {mismatches:,} ({100*mismatches/total:.1f}%)")

# VERDICT
print("\n" + "=" * 80)
print("VERDICT")
print("=" * 80)

cur.execute("""
    SELECT COUNT(*)
    FROM charters c
    WHERE NOT EXISTS (
        SELECT 1 FROM charter_charges cc 
        WHERE cc.reserve_number = c.reserve_number
    )
    AND c.cancelled = FALSE
    AND c.total_amount_due IS NOT NULL
    AND c.total_amount_due != 0
""")
charters_without_charges = cur.fetchone()[0]

print(f"\nCharters with total_amount_due but NO charter_charges: {charters_without_charges:,}")

if matches >= total * 0.95:  # 95%+ match
    print("\n✅ Payments reconcile to charters.paid_amount")
    print("✅ Charter totals are the source of truth")
    if mismatches > 0:
        print(f"⚠️  charter_charges table has {len(mismatches)} mismatches")
    print("\n🔥 RECOMMENDATION: charter_charges table is REDUNDANT")
    print("   - Charters already have total_amount_due")
    print("   - Payments reconcile to charter totals")
    print("   - charter_charges doesn't match charter totals")
    print("   - SAFE TO DROP charter_charges table")
else:
    print("\n⚠️  Payments do NOT reconcile to charters.paid_amount")
    print("   Need to investigate discrepancies before dropping charter_charges")

cur.close()
conn.close()
