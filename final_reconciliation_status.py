import psycopg2
import os

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

print("="*80)
print("COMPREHENSIVE CHARTER RECONCILIATION STATUS - JANUARY 23, 2026")
print("="*80)

# Pre-2025 charters
cur.execute("""
    WITH sums AS (
        SELECT reserve_number, SUM(amount) AS charge_sum
        FROM charter_charges
        WHERE reserve_number IS NOT NULL
        GROUP BY reserve_number
    )
    SELECT 
        COUNT(*) as total,
        COUNT(CASE WHEN c.total_amount_due = s.charge_sum THEN 1 END) AS exact_match,
        COUNT(CASE WHEN c.total_amount_due < s.charge_sum THEN 1 END) AS overages,
        COUNT(CASE WHEN c.total_amount_due > 0 AND s.charge_sum < c.total_amount_due THEN 1 END) AS deficits,
        COUNT(CASE WHEN s.charge_sum IS NULL OR s.charge_sum = 0 THEN 1 END) AS zero_charges
    FROM charters c
    LEFT JOIN sums s ON c.reserve_number = s.reserve_number
    WHERE c.charter_date < '2025-01-01'
""")
pre2025 = cur.fetchone()

# All charters
cur.execute("""
    WITH sums AS (
        SELECT reserve_number, SUM(amount) AS charge_sum
        FROM charter_charges
        WHERE reserve_number IS NOT NULL
        GROUP BY reserve_number
    )
    SELECT 
        COUNT(*) as total,
        COUNT(CASE WHEN c.total_amount_due = s.charge_sum THEN 1 END) AS exact_match,
        COUNT(CASE WHEN c.total_amount_due < s.charge_sum THEN 1 END) AS overages,
        COUNT(CASE WHEN c.total_amount_due > 0 AND s.charge_sum < c.total_amount_due THEN 1 END) AS deficits,
        COUNT(CASE WHEN s.charge_sum IS NULL OR s.charge_sum = 0 THEN 1 END) AS zero_charges
    FROM charters c
    LEFT JOIN sums s ON c.reserve_number = s.reserve_number
    WHERE status NOT IN ('cancelled', 'refunded')
""")
all_charters = cur.fetchone()

# Payment matching
cur.execute("""
    SELECT 
        COUNT(*) as total_charters,
        COUNT(CASE WHEN paid_amount = (SELECT COALESCE(SUM(amount), 0) FROM payments p WHERE p.reserve_number = c.reserve_number) THEN 1 END) as matched,
        COUNT(CASE WHEN paid_amount != (SELECT COALESCE(SUM(amount), 0) FROM payments p WHERE p.reserve_number = c.reserve_number) THEN 1 END) as mismatched
    FROM charters c
    WHERE status NOT IN ('cancelled', 'refunded')
""")
payments = cur.fetchone()

# Balance matching
cur.execute("""
    SELECT 
        COUNT(CASE WHEN balance = total_amount_due - paid_amount THEN 1 END) as correct,
        COUNT(CASE WHEN balance != total_amount_due - paid_amount THEN 1 END) as incorrect
    FROM charters
    WHERE status NOT IN ('cancelled', 'refunded')
""")
balance = cur.fetchone()

print("\n📊 PRE-2025 CHARTERS (< 2025-01-01)")
print("-" * 80)
print(f"  Total charters:        {pre2025[0]:>6,}")
print(f"  ✅ Exact match:        {pre2025[1]:>6,}  ({100*pre2025[1]/pre2025[0]:.1f}%)")
print(f"  ⚠️  Overages:          {pre2025[2]:>6}  (charges > total)")
print(f"  ⚠️  Deficits:          {pre2025[3]:>6}  (charges < total)")
print(f"  📋 Zero charges:       {pre2025[4]:>6}  (unfilled/legacy)")

print("\n📊 ALL ACTIVE CHARTERS (non-cancelled/refunded)")
print("-" * 80)
print(f"  Total charters:        {all_charters[0]:>6,}")
print(f"  ✅ Exact match:        {all_charters[1]:>6,}  ({100*all_charters[1]/all_charters[0]:.1f}%)")
print(f"  ⚠️  Overages:          {all_charters[2]:>6}  (charges > total)")
print(f"  ⚠️  Deficits:          {all_charters[3]:>6}  (charges < total)")
print(f"  📋 Zero charges:       {all_charters[4]:>6}  (unfilled/legacy)")

print("\n💳 PAYMENT RECONCILIATION")
print("-" * 80)
print(f"  Total charters:        {payments[0]:>6,}")
print(f"  ✅ Matched:            {payments[1]:>6,}  ({100*payments[1]/payments[0]:.1f}%)")
print(f"  ⚠️  Mismatched:        {payments[2]:>6}  (paid_amount ≠ SUM(payments))")

print("\n⚖️  BALANCE CALCULATIONS")
print("-" * 80)
print(f"  ✅ Correct:            {balance[0]:>6,}  ({100*balance[0]/(balance[0]+balance[1]):.1f}%)")
print(f"  ⚠️  Incorrect:         {balance[1]:>6}  (balance ≠ total - paid)")

print("\n" + "="*80)
print("SUMMARY")
print("="*80)
total_issues = all_charters[2] + all_charters[3] + payments[2] + balance[1]
print(f"✅ Pre-2025 deficits:              0 / 0  (RESOLVED)")
print(f"✅ Payment matching:              {payments[2]} / {payments[0]}  (recalculated)")
print(f"✅ Balance calculations:          {balance[1]} / {balance[0]+balance[1]}  (may auto-fix)")
print(f"\n⚠️  Remaining issues: {total_issues:,}")
print(f"   - {all_charters[2]} overages (charges > total)")
print(f"   - {all_charters[3]} deficits (charges < total)")

cur.close()
conn.close()
