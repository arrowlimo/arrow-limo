import psycopg2
import os
from datetime import datetime

conn = psycopg2.connect(
    host=os.getenv('DB_HOST', 'localhost'),
    dbname=os.getenv('DB_NAME', 'almsdata'),
    user=os.getenv('DB_USER', 'postgres'),
    password=os.getenv('DB_PASSWORD', '***REMOVED***')
)
cur = conn.cursor()

print("=" * 80)
print("COMPREHENSIVE PAYMENT AUDIT")
print("=" * 80)

# 1. Get total payment statistics
print("\n1. OVERALL PAYMENT STATISTICS:")
print("-" * 80)
cur.execute("""
    SELECT 
        COUNT(*) as total_payments,
        COUNT(DISTINCT reserve_number) as unique_reserves,
        SUM(amount) as total_amount,
        COUNT(CASE WHEN reserve_number IS NULL THEN 1 END) as null_reserve,
        COUNT(CASE WHEN charter_id IS NULL THEN 1 END) as null_charter
    FROM payments
""")
stats = cur.fetchone()
print(f"Total Payments: {stats[0]:,}")
print(f"Unique Reserve Numbers: {stats[1]:,}")
print(f"Total Amount: ${stats[2]:,.2f}")
print(f"Payments with NULL reserve_number: {stats[3]:,}")
print(f"Payments with NULL charter_id: {stats[4]:,}")

# 2. Charters with payment mismatches (paid_amount != sum of payments)
print("\n2. CHARTERS WITH PAYMENT MISMATCHES:")
print("-" * 80)
cur.execute("""
    SELECT 
        c.reserve_number,
        c.charter_id,
        c.charter_date,
        c.total_amount_due,
        c.paid_amount as charter_paid,
        COALESCE(SUM(p.amount), 0) as actual_payments,
        c.paid_amount - COALESCE(SUM(p.amount), 0) as difference
    FROM charters c
    LEFT JOIN payments p ON p.reserve_number = c.reserve_number
    WHERE c.reserve_number IS NOT NULL
    GROUP BY c.charter_id, c.reserve_number, c.charter_date, c.total_amount_due, c.paid_amount
    HAVING ABS(c.paid_amount - COALESCE(SUM(p.amount), 0)) > 0.01
    ORDER BY ABS(c.paid_amount - COALESCE(SUM(p.amount), 0)) DESC
    LIMIT 50
""")
mismatches = cur.fetchall()
print(f"Found {len(mismatches)} charters with payment mismatches")
if mismatches:
    print("\nTop 20 mismatches:")
    for m in mismatches[:20]:
        print(f"  {m[0]} | Date: {m[2]} | Due: ${m[3]} | Charter Paid: ${m[4]} | Actual: ${m[5]} | Diff: ${m[6]}")

# 3. Payments linked to non-existent charters
print("\n3. PAYMENTS LINKED TO NON-EXISTENT CHARTERS:")
print("-" * 80)
cur.execute("""
    SELECT 
        p.payment_id,
        p.reserve_number,
        p.amount,
        p.payment_date,
        p.payment_key
    FROM payments p
    LEFT JOIN charters c ON c.reserve_number = p.reserve_number
    WHERE p.reserve_number IS NOT NULL
    AND c.reserve_number IS NULL
    LIMIT 50
""")
orphaned = cur.fetchall()
if orphaned:
    print(f"Found {len(orphaned)} payments linked to non-existent charters")
    for o in orphaned[:10]:
        print(f"  Payment {o[0]} | Reserve: {o[1]} | ${o[2]} | Date: {o[3]} | Key: {o[4]}")
else:
    print("No orphaned payments found")

# 4. Duplicate payment keys (same key used multiple times)
print("\n4. DUPLICATE PAYMENT KEYS:")
print("-" * 80)
cur.execute("""
    SELECT 
        payment_key,
        COUNT(*) as count,
        SUM(amount) as total_amount,
        STRING_AGG(DISTINCT reserve_number, ', ' ORDER BY reserve_number) as reserves
    FROM payments
    WHERE payment_key IS NOT NULL
    AND payment_key != ''
    GROUP BY payment_key
    HAVING COUNT(*) > 1
    ORDER BY COUNT(*) DESC
    LIMIT 20
""")
dupes = cur.fetchall()
if dupes:
    print(f"Found {len(dupes)} payment keys used multiple times")
    for d in dupes[:10]:
        print(f"  Key: {d[0]} | Used {d[1]} times | Total: ${d[2]} | Reserves: {d[3][:80]}")
else:
    print("No duplicate payment keys found")

# 5. ETR: payments (e-transfer imports) - check if properly linked
print("\n5. ETR: PAYMENT ANALYSIS (E-Transfer Imports):")
print("-" * 80)
cur.execute("""
    SELECT 
        COUNT(*) as total_etr,
        COUNT(CASE WHEN reserve_number IS NOT NULL THEN 1 END) as linked,
        COUNT(CASE WHEN reserve_number IS NULL THEN 1 END) as unlinked,
        SUM(amount) as total_amount
    FROM payments
    WHERE payment_key LIKE 'ETR:%'
""")
etr = cur.fetchone()
print(f"Total ETR payments: {etr[0]:,}")
print(f"Linked to charters: {etr[1]:,}")
print(f"Unlinked: {etr[2]:,}")
print(f"Total Amount: ${etr[3]:,.2f}")

# 6. Sample ETR payments to verify they're properly matched
print("\n6. SAMPLE ETR PAYMENTS (checking if banking matches charter dates):")
print("-" * 80)
cur.execute("""
    SELECT 
        p.payment_id,
        p.reserve_number,
        p.amount,
        p.payment_date,
        p.payment_key,
        c.charter_date,
        bt.transaction_date,
        bt.description
    FROM payments p
    LEFT JOIN charters c ON c.reserve_number = p.reserve_number
    LEFT JOIN banking_transactions bt ON bt.transaction_id::text = REPLACE(p.payment_key, 'ETR:', '')
    WHERE p.payment_key LIKE 'ETR:%'
    AND p.reserve_number IS NOT NULL
    ORDER BY p.payment_date DESC
    LIMIT 20
""")
etr_samples = cur.fetchall()
if etr_samples:
    print("Sample ETR payments:")
    for e in etr_samples[:10]:
        date_match = "✓" if e[5] and e[6] and abs((e[5] - e[6]).days) <= 90 else "✗"
        print(f"  {date_match} Payment {e[0]} | Res: {e[1]} | ${e[2]} | Charter: {e[5]} | Bank: {e[6]}")
        if e[7]:
            print(f"      Bank desc: {e[7][:80]}")

# 7. Payments with mismatched dates (payment date far from charter date)
print("\n7. PAYMENTS WITH DATE MISMATCHES (>90 days difference):")
print("-" * 80)
cur.execute("""
    SELECT 
        p.payment_id,
        p.reserve_number,
        p.amount,
        p.payment_date,
        c.charter_date,
        ABS(p.payment_date - c.charter_date) as days_diff
    FROM payments p
    JOIN charters c ON c.reserve_number = p.reserve_number
    WHERE ABS(p.payment_date - c.charter_date) > 90
    ORDER BY days_diff DESC
    LIMIT 20
""")
date_mismatches = cur.fetchall()
if date_mismatches:
    print(f"Found {len(date_mismatches)} payments with >90 day date difference")
    for dm in date_mismatches[:10]:
        print(f"  Payment {dm[0]} | Res: {dm[1]} | ${dm[2]} | Pay: {dm[3]} | Charter: {dm[4]} | Diff: {int(dm[5])} days")
else:
    print("No significant date mismatches found")

# 8. Charters with excessive payments (paid > 2x total_due)
print("\n8. CHARTERS WITH EXCESSIVE PAYMENTS (>2x total due):")
print("-" * 80)
cur.execute("""
    SELECT 
        c.reserve_number,
        c.charter_date,
        c.total_amount_due,
        COALESCE(SUM(p.amount), 0) as total_paid,
        COUNT(p.payment_id) as payment_count
    FROM charters c
    LEFT JOIN payments p ON p.reserve_number = c.reserve_number
    WHERE c.total_amount_due > 0
    GROUP BY c.reserve_number, c.charter_date, c.total_amount_due
    HAVING COALESCE(SUM(p.amount), 0) > c.total_amount_due * 2
    ORDER BY (COALESCE(SUM(p.amount), 0) - c.total_amount_due) DESC
    LIMIT 20
""")
excessive = cur.fetchall()
if excessive:
    print(f"Found {len(excessive)} charters with excessive payments")
    for ex in excessive[:10]:
        print(f"  {ex[0]} | Date: {ex[1]} | Due: ${ex[2]} | Paid: ${ex[3]} | Payments: {ex[4]} | Overpaid: ${ex[3] - ex[2]:.2f}")
else:
    print("No charters with excessive payments found")

# 9. Summary of payment methods and their linkage quality
print("\n9. PAYMENT METHOD LINKAGE QUALITY:")
print("-" * 80)
cur.execute("""
    SELECT 
        COALESCE(payment_method, 'unknown') as method,
        COUNT(*) as count,
        SUM(amount) as total,
        COUNT(CASE WHEN reserve_number IS NULL THEN 1 END) as unlinked,
        ROUND(100.0 * COUNT(CASE WHEN reserve_number IS NULL THEN 1 END) / COUNT(*), 2) as unlinked_pct
    FROM payments
    GROUP BY payment_method
    ORDER BY count DESC
""")
methods = cur.fetchall()
for m in methods:
    print(f"  {m[0]:20} | Count: {m[1]:6,} | Total: ${m[2]:12,.2f} | Unlinked: {m[3]:5,} ({m[4]}%)")

cur.close()
conn.close()

print("\n" + "=" * 80)
print("AUDIT COMPLETE")
print("=" * 80)
print("\nRECOMMENDATIONS:")
print("1. Fix payment mismatches for charters (recalculate paid_amount)")
print("2. Investigate ETR: payment linkages with >90 day date differences")
print("3. Review charters with excessive payments (>2x total due)")
print("4. Clean up orphaned payments (linked to non-existent charters)")
