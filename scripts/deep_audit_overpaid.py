"""
Deep audit of overpaid charters to find the root cause.
Check for patterns in the remaining $933K credits.
"""

import psycopg2
import os

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REDACTED***')
    )

conn = get_db_connection()
cur = conn.cursor()

print("=" * 80)
print("DEEP AUDIT: REMAINING OVERPAID CHARTERS")
print("=" * 80)

# Get top overpaid charter for analysis
cur.execute("""
    SELECT charter_id, reserve_number, charter_date, total_amount_due, paid_amount, balance
    FROM charters
    WHERE balance < 0
    ORDER BY balance
    LIMIT 1
""")

charter = cur.fetchone()
charter_id, reserve, charter_date, total_due, paid, balance = charter

print(f"\n📋 ANALYZING TOP OVERPAID CHARTER: {reserve}")
print(f"   Date: {charter_date}")
print(f"   Total due: ${total_due:,.2f}")
print(f"   Paid: ${paid:,.2f}")
print(f"   Balance: ${balance:,.2f}")

# Check charter_charges
cur.execute("""
    SELECT COUNT(*), SUM(amount), ARRAY_AGG(description || ': $' || amount::text)
    FROM charter_charges
    WHERE charter_id = %s
""", (charter_id,))

charge_count, charge_sum, charge_details = cur.fetchone()
print(f"\n💰 CHARTER_CHARGES:")
print(f"   Count: {charge_count}")
print(f"   Sum: ${charge_sum or 0:,.2f}")
if charge_details and charge_details[0]:
    print(f"   Details: {charge_details[:3]}")

# Check if charge sum matches total_amount_due
if charge_sum:
    print(f"\n[WARN]  CHARGE MISMATCH:")
    print(f"   charter.total_amount_due: ${total_due:,.2f}")
    print(f"   SUM(charter_charges):     ${charge_sum:,.2f}")
    print(f"   Difference: ${total_due - charge_sum:,.2f}")

# Check payments
cur.execute("""
    SELECT payment_id, payment_date, amount, payment_method, notes
    FROM payments
    WHERE reserve_number = %s
    ORDER BY payment_date
""", (reserve,))

payments = cur.fetchall()
print(f"\n💵 PAYMENTS ({len(payments)} total):")
for p in payments[:10]:  # Show first 10
    notes_short = (p[4][:50] + '...') if p[4] and len(p[4]) > 50 else (p[4] or '')
    print(f"   {p[1]} - ${p[2]:,.2f} ({p[3] or 'unknown'}) {notes_short}")

if len(payments) > 10:
    print(f"   ... and {len(payments)-10} more payments")

# Check for duplicate payment patterns
cur.execute("""
    SELECT payment_date, amount, COUNT(*) as dup_count
    FROM payments
    WHERE reserve_number = %s
    GROUP BY payment_date, amount
    HAVING COUNT(*) > 1
""", (reserve,))

dups = cur.fetchall()
if dups:
    print(f"\n[WARN]  DUPLICATE PAYMENTS STILL EXIST:")
    for d in dups:
        print(f"   {d[0]} - ${d[1]:,.2f} x{d[2]} times")

# Now check patterns across ALL overpaid charters
print(f"\n{'='*80}")
print("PATTERN ANALYSIS: ALL OVERPAID CHARTERS")
print("=" * 80)

# Pattern 1: Total_amount_due doesn't match charter_charges sum
cur.execute("""
    SELECT 
        c.reserve_number,
        c.total_amount_due,
        COALESCE(SUM(cc.amount), 0) as charge_sum,
        c.total_amount_due - COALESCE(SUM(cc.amount), 0) as mismatch,
        c.paid_amount,
        c.balance
    FROM charters c
    LEFT JOIN charter_charges cc ON cc.charter_id = c.charter_id
    WHERE c.balance < 0
    GROUP BY c.charter_id, c.reserve_number, c.total_amount_due, c.paid_amount, c.balance
    HAVING c.total_amount_due != COALESCE(SUM(cc.amount), 0)
    ORDER BY ABS(c.total_amount_due - COALESCE(SUM(cc.amount), 0)) DESC
    LIMIT 20
""")

mismatches = cur.fetchall()
if mismatches:
    print(f"\n[WARN]  PATTERN 1: total_amount_due ≠ SUM(charter_charges)")
    print(f"   Found {len(mismatches)} charters")
    print(f"\n{'Reserve':<10} {'Total Due':>12} {'Charge Sum':>12} {'Mismatch':>12} {'Paid':>12} {'Balance':>12}")
    print("-" * 80)
    
    total_mismatch = 0
    for row in mismatches[:10]:
        print(f"{row[0]:<10} ${row[1]:>10,.2f} ${row[2]:>10,.2f} ${row[3]:>10,.2f} ${row[4]:>10,.2f} ${row[5]:>10,.2f}")
        total_mismatch += abs(row[3])
    
    print(f"\nTotal mismatch in sample: ${total_mismatch:,.2f}")

# Pattern 2: Check if there are still more duplicates we missed
cur.execute("""
    WITH payment_groups AS (
        SELECT 
            reserve_number,
            payment_date,
            amount,
            COUNT(*) as payment_count,
            ARRAY_AGG(payment_id) as payment_ids
        FROM payments
        WHERE reserve_number IN (
            SELECT reserve_number FROM charters WHERE balance < 0
        )
        GROUP BY reserve_number, payment_date, amount
        HAVING COUNT(*) > 1
    )
    SELECT COUNT(*), SUM((payment_count - 1) * amount)
    FROM payment_groups
""")

dup_sets, dup_amount = cur.fetchone()
if dup_sets and dup_sets > 0:
    print(f"\n[WARN]  PATTERN 2: MORE DUPLICATE PAYMENTS FOUND")
    print(f"   Duplicate sets: {dup_sets}")
    print(f"   Duplicate amount: ${dup_amount or 0:,.2f}")

# Pattern 3: Charters with no charges but large payments
cur.execute("""
    SELECT 
        c.reserve_number,
        c.total_amount_due,
        c.paid_amount,
        c.balance,
        COUNT(cc.charge_id) as charge_count
    FROM charters c
    LEFT JOIN charter_charges cc ON cc.charter_id = c.charter_id
    WHERE c.balance < 0
    GROUP BY c.charter_id, c.reserve_number, c.total_amount_due, c.paid_amount, c.balance
    HAVING COUNT(cc.charge_id) = 0
    ORDER BY c.paid_amount DESC
    LIMIT 10
""")

no_charges = cur.fetchall()
if no_charges:
    print(f"\n[WARN]  PATTERN 3: Charters with NO charges but payments")
    print(f"\n{'Reserve':<10} {'Total Due':>12} {'Paid':>12} {'Balance':>12} {'Charges'}")
    print("-" * 70)
    for row in no_charges:
        print(f"{row[0]:<10} ${row[1]:>10,.2f} ${row[2]:>10,.2f} ${row[3]:>10,.2f} {row[4]}")

cur.close()
conn.close()

print("\n" + "=" * 80)
print("AUDIT COMPLETE")
print("=" * 80)
