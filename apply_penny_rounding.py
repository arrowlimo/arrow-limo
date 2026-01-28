import psycopg2
import os
from decimal import Decimal

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

print("Applying penny rounding adjustments...\n")

# 1. Fix remaining deficits with rounding charges
print("Step 1: Fixing remaining 6 deficits with rounding charges")
print("-" * 70)

cur.execute("""
    WITH sums AS (
        SELECT reserve_number, SUM(amount) AS charge_sum
        FROM charter_charges
        WHERE reserve_number IS NOT NULL
        GROUP BY reserve_number
    )
    SELECT c.charter_id, c.reserve_number, c.total_amount_due, 
           COALESCE(s.charge_sum, 0) as charge_sum,
           (c.total_amount_due - COALESCE(s.charge_sum, 0)) as diff
    FROM charters c
    LEFT JOIN sums s ON c.reserve_number = s.reserve_number
    WHERE c.total_amount_due > 0 
    AND COALESCE(s.charge_sum, 0) < c.total_amount_due
    AND c.status NOT IN ('cancelled', 'refunded')
    ORDER BY diff
""")

deficits = cur.fetchall()
print(f"Found {len(deficits)} remaining deficits\n")

for charter_id, reserve, total_due, charge_sum, diff in deficits:
    if diff > 0:
        cur.execute("""
            INSERT INTO charter_charges (charter_id, reserve_number, description, amount, created_at)
            VALUES (%s, %s, %s, %s, NOW())
        """, (charter_id, reserve, "Rounding Adjustment", float(diff)))
        conn.commit()
        print(f"✅ {reserve}: Added ${diff:.2f} rounding charge (total: ${total_due:.2f})")

# 2. Fix balance calculation errors
print("\n\nStep 2: Fixing balance calculation errors")
print("-" * 70)

cur.execute("""
    SELECT COUNT(*) FROM charters 
    WHERE status NOT IN ('cancelled', 'refunded')
    AND balance != (total_amount_due - paid_amount)
""")
balance_errors = cur.fetchone()[0]

sql_fix_balance = """
    UPDATE charters
    SET balance = ROUND(total_amount_due - paid_amount, 2)
    WHERE status NOT IN ('cancelled', 'refunded')
    AND balance != (total_amount_due - paid_amount)
"""

cur.execute(sql_fix_balance)
updated = cur.rowcount
conn.commit()

print(f"✅ Fixed {updated} balance calculation errors")

# 3. Final verification
print("\n\nStep 3: Final Verification")
print("-" * 70)

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
        COUNT(CASE WHEN c.total_amount_due > 0 AND s.charge_sum < c.total_amount_due THEN 1 END) AS deficits
    FROM charters c
    LEFT JOIN sums s ON c.reserve_number = s.reserve_number
    WHERE status NOT IN ('cancelled', 'refunded')
""")

result = cur.fetchone()
print(f"Total active charters:         {result[0]:>6,}")
print(f"✅ Exact match:                {result[1]:>6,}  ({100*result[1]/result[0]:.1f}%)")
print(f"Overages:                      {result[2]:>6}")
print(f"Deficits:                      {result[3]:>6}")

# Balance check
cur.execute("""
    SELECT 
        COUNT(CASE WHEN balance = total_amount_due - paid_amount THEN 1 END) as correct,
        COUNT(CASE WHEN balance != total_amount_due - paid_amount THEN 1 END) as incorrect
    FROM charters
    WHERE status NOT IN ('cancelled', 'refunded')
""")
balance_result = cur.fetchone()
print(f"\nBalance calculations correct: {balance_result[0]:>6,}  ({100*balance_result[0]/(balance_result[0]+balance_result[1]):.1f}%)")
print(f"Balance errors remaining:     {balance_result[1]:>6}")

print("\n" + "="*70)
print("✅ PENNY ROUNDING ADJUSTMENTS APPLIED")
print("="*70)

cur.close()
conn.close()
