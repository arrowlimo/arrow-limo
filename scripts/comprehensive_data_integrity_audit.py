"""
Comprehensive PostgreSQL Data Integrity Audit
Identifies duplicates, incorrect totals, orphaned records, and data corruption
"""
import psycopg2
import os
from decimal import Decimal
from collections import defaultdict

pg_conn = psycopg2.connect(
    host=os.getenv('DB_HOST', 'localhost'),
    database=os.getenv('DB_NAME', 'almsdata'),
    user=os.getenv('DB_USER', 'postgres'),
    password=os.getenv('DB_PASSWORD', '***REDACTED***')
)
pg_cur = pg_conn.cursor()

print("=" * 120)
print("COMPREHENSIVE POSTGRESQL DATA INTEGRITY AUDIT")
print("=" * 120)
print()

issues = []

# ============================================================================
# 1. DUPLICATE PAYMENTS CHECK
# ============================================================================
print("1. CHECKING FOR DUPLICATE PAYMENTS...")
print("-" * 120)

# Check for exact duplicates (same reserve, amount, date)
pg_cur.execute("""
    SELECT reserve_number, amount, payment_date, COUNT(*) as dup_count,
           STRING_AGG(payment_id::text, ', ') as payment_ids
    FROM payments
    WHERE reserve_number IS NOT NULL
      AND amount IS NOT NULL
      AND payment_date IS NOT NULL
    GROUP BY reserve_number, amount, payment_date
    HAVING COUNT(*) > 1
    ORDER BY COUNT(*) DESC, amount DESC
""")
exact_dups = pg_cur.fetchall()

if exact_dups:
    print(f"   ⚠️  Found {len(exact_dups)} sets of EXACT DUPLICATE payments")
    total_dup_amount = sum(row[1] * (row[3] - 1) for row in exact_dups)
    print(f"   💰 Duplicate amount: ${total_dup_amount:,.2f}")
    print()
    print("   Top 10 duplicate sets:")
    for reserve, amount, date, count, ids in exact_dups[:10]:
        print(f"      Reserve {reserve}: ${amount:,.2f} on {date} ({count} copies) - IDs: {ids}")
    if len(exact_dups) > 10:
        print(f"      ... and {len(exact_dups) - 10} more duplicate sets")
    issues.append(f"DUPLICATE_PAYMENTS: {len(exact_dups)} sets, ${total_dup_amount:,.2f} duplicate amount")
else:
    print("   ✅ No exact duplicate payments found")

print()

# Check for suspicious duplicates (same reserve, same amount, dates within 3 days)
pg_cur.execute("""
    WITH payment_pairs AS (
        SELECT p1.payment_id as id1, p2.payment_id as id2,
               p1.reserve_number, p1.amount, p1.payment_date as date1, p2.payment_date as date2
        FROM payments p1
        JOIN payments p2 ON p1.reserve_number = p2.reserve_number
                         AND p1.amount = p2.amount
                         AND p1.payment_id < p2.payment_id
                         AND ABS(DATE_PART('day', p2.payment_date::timestamp - p1.payment_date::timestamp)) <= 3
        WHERE p1.reserve_number IS NOT NULL AND p1.amount IS NOT NULL
    )
    SELECT COUNT(*) FROM payment_pairs
""")
suspicious_dups = pg_cur.fetchone()[0]

if suspicious_dups > 0:
    print(f"   ⚠️  Found {suspicious_dups} SUSPICIOUS near-duplicate payments (same reserve, amount, within 3 days)")
    issues.append(f"SUSPICIOUS_DUPLICATES: {suspicious_dups} payment pairs")
else:
    print("   ✅ No suspicious near-duplicate payments")

print()

# ============================================================================
# 2. CHARTER BALANCE INTEGRITY CHECK
# ============================================================================
print("2. CHECKING CHARTER BALANCE CALCULATIONS...")
print("-" * 120)

pg_cur.execute("""
    WITH charter_calcs AS (
        SELECT 
            c.charter_id,
            c.reserve_number,
            c.total_amount_due,
            c.paid_amount as stored_paid,
            c.balance as stored_balance,
            COALESCE(SUM(p.amount), 0) as actual_paid,
            c.total_amount_due - COALESCE(SUM(p.amount), 0) as calculated_balance
        FROM charters c
        LEFT JOIN payments p ON p.reserve_number = c.reserve_number
        GROUP BY c.charter_id, c.reserve_number, c.total_amount_due, c.paid_amount, c.balance
    )
    SELECT 
        charter_id, reserve_number, total_amount_due,
        stored_paid, actual_paid, stored_paid - actual_paid as paid_diff,
        stored_balance, calculated_balance, stored_balance - calculated_balance as balance_diff
    FROM charter_calcs
    WHERE ABS(stored_paid - actual_paid) > 0.02
       OR ABS(stored_balance - calculated_balance) > 0.02
    ORDER BY ABS(stored_balance - calculated_balance) DESC
""")
balance_issues = pg_cur.fetchall()

if balance_issues:
    print(f"   ⚠️  Found {len(balance_issues)} charters with INCORRECT balance calculations")
    print()
    print("   Top 20 worst balance discrepancies:")
    print(f"   {'Reserve':<12} {'Charter':<8} {'Total Due':<12} {'Stored Paid':<12} {'Actual Paid':<12} {'Balance Diff':<12}")
    print("   " + "-" * 80)
    for issue in balance_issues[:20]:
        print(f"   {issue[1]:<12} {issue[0]:<8} ${issue[2]:>10,.2f} ${issue[3]:>10,.2f} ${issue[4]:>10,.2f} ${issue[8]:>10,.2f}")
    if len(balance_issues) > 20:
        print(f"   ... and {len(balance_issues) - 20} more")
    
    total_balance_error = sum(abs(issue[8]) for issue in balance_issues)
    issues.append(f"BALANCE_ERRORS: {len(balance_issues)} charters, ${total_balance_error:,.2f} total error")
else:
    print("   ✅ All charter balances calculated correctly")

print()

# ============================================================================
# 3. ORPHANED PAYMENTS CHECK
# ============================================================================
print("3. CHECKING FOR ORPHANED PAYMENTS...")
print("-" * 120)

pg_cur.execute("""
    SELECT COUNT(*), SUM(amount)
    FROM payments p
    WHERE p.reserve_number IS NOT NULL
      AND NOT EXISTS (
          SELECT 1 FROM charters c WHERE c.reserve_number = p.reserve_number
      )
""")
orphaned_count, orphaned_amount = pg_cur.fetchone()

if orphaned_count and orphaned_count > 0:
    print(f"   ⚠️  Found {orphaned_count} ORPHANED payments (no matching charter)")
    print(f"   💰 Total orphaned amount: ${orphaned_amount:,.2f}")
    
    # Show sample
    pg_cur.execute("""
        SELECT payment_id, reserve_number, amount, payment_date
        FROM payments p
        WHERE p.reserve_number IS NOT NULL
          AND NOT EXISTS (
              SELECT 1 FROM charters c WHERE c.reserve_number = p.reserve_number
          )
        ORDER BY amount DESC
        LIMIT 10
    """)
    orphaned_samples = pg_cur.fetchall()
    print()
    print("   Sample orphaned payments:")
    for pmt in orphaned_samples:
        print(f"      Payment {pmt[0]}: Reserve {pmt[1]}, ${pmt[2]:,.2f} on {pmt[3]}")
    
    issues.append(f"ORPHANED_PAYMENTS: {orphaned_count} payments, ${orphaned_amount:,.2f}")
else:
    print("   ✅ No orphaned payments")

print()

# Check for NULL reserve_number payments
pg_cur.execute("""
    SELECT COUNT(*), SUM(amount)
    FROM payments
    WHERE reserve_number IS NULL AND amount IS NOT NULL
""")
null_reserve_count, null_reserve_amount = pg_cur.fetchone()

if null_reserve_count and null_reserve_count > 0:
    print(f"   ⚠️  Found {null_reserve_count} payments with NULL reserve_number")
    print(f"   💰 Total amount: ${null_reserve_amount or 0:,.2f}")
    issues.append(f"NULL_RESERVE_PAYMENTS: {null_reserve_count} payments")
else:
    print("   ✅ All payments have reserve_number")

print()

# ============================================================================
# 4. CHARTER CHARGES INTEGRITY CHECK
# ============================================================================
print("4. CHECKING CHARTER CHARGES TOTALS...")
print("-" * 120)

pg_cur.execute("""
    WITH charge_totals AS (
        SELECT 
            c.charter_id,
            c.reserve_number,
            c.total_amount_due as stored_total,
            COALESCE(SUM(cc.amount), 0) as charges_sum
        FROM charters c
        LEFT JOIN charter_charges cc ON cc.charter_id = c.charter_id
        GROUP BY c.charter_id, c.reserve_number, c.total_amount_due
    )
    SELECT charter_id, reserve_number, stored_total, charges_sum,
           stored_total - charges_sum as difference
    FROM charge_totals
    WHERE ABS(stored_total - charges_sum) > 0.02
    ORDER BY ABS(stored_total - charges_sum) DESC
""")
charge_issues = pg_cur.fetchall()

if charge_issues:
    print(f"   ⚠️  Found {len(charge_issues)} charters where total_amount_due != SUM(charter_charges)")
    print()
    print("   Top 20 charge total discrepancies:")
    print(f"   {'Reserve':<12} {'Charter':<8} {'Stored Total':<15} {'Charges Sum':<15} {'Difference':<12}")
    print("   " + "-" * 80)
    for issue in charge_issues[:20]:
        print(f"   {issue[1]:<12} {issue[0]:<8} ${issue[2]:>13,.2f} ${issue[3]:>13,.2f} ${issue[4]:>10,.2f}")
    if len(charge_issues) > 20:
        print(f"   ... and {len(charge_issues) - 20} more")
    
    total_charge_error = sum(abs(issue[4]) for issue in charge_issues)
    issues.append(f"CHARGE_TOTAL_ERRORS: {len(charge_issues)} charters, ${total_charge_error:,.2f} total error")
else:
    print("   ✅ All charter charge totals match")

print()

# ============================================================================
# 5. PAYMENT METHOD CONSISTENCY CHECK
# ============================================================================
print("5. CHECKING PAYMENT METHOD CONSISTENCY...")
print("-" * 120)

pg_cur.execute("""
    SELECT payment_method, COUNT(*), SUM(amount)
    FROM payments
    WHERE payment_method IS NOT NULL
    GROUP BY payment_method
    ORDER BY COUNT(*) DESC
""")
payment_methods = pg_cur.fetchall()

print("   Payment method distribution:")
for method, count, total in payment_methods:
    print(f"      {method or 'NULL':<25} {count:>6} payments, ${total or 0:>12,.2f}")

# Check for unusual payment methods
pg_cur.execute("""
    SELECT COUNT(*)
    FROM payments
    WHERE payment_method IS NULL OR payment_method = 'unknown'
""")
unknown_methods = pg_cur.fetchone()[0]

if unknown_methods > 100:
    print(f"   ⚠️  {unknown_methods} payments have NULL or 'unknown' payment method")
    issues.append(f"UNKNOWN_PAYMENT_METHODS: {unknown_methods} payments")

print()

# ============================================================================
# 6. NEGATIVE AMOUNTS CHECK
# ============================================================================
print("6. CHECKING FOR NEGATIVE AMOUNTS...")
print("-" * 120)

pg_cur.execute("""
    SELECT COUNT(*), SUM(amount)
    FROM payments
    WHERE amount < 0
""")
negative_payments = pg_cur.fetchone()

if negative_payments[0] and negative_payments[0] > 0:
    print(f"   ℹ️  Found {negative_payments[0]} negative payments (refunds)")
    print(f"   💰 Total refund amount: ${negative_payments[1]:,.2f}")
    
    # Check if these have matching positive payments
    pg_cur.execute("""
        SELECT p1.payment_id, p1.reserve_number, p1.amount, p1.payment_date
        FROM payments p1
        WHERE p1.amount < 0
          AND NOT EXISTS (
              SELECT 1 FROM payments p2
              WHERE p2.reserve_number = p1.reserve_number
                AND p2.amount = -p1.amount
                AND p2.payment_date <= p1.payment_date
          )
        ORDER BY p1.amount
        LIMIT 10
    """)
    orphan_refunds = pg_cur.fetchall()
    
    if orphan_refunds:
        print(f"   ⚠️  Found {len(orphan_refunds)} refunds WITHOUT matching positive payments:")
        for pmt in orphan_refunds:
            print(f"      Payment {pmt[0]}: Reserve {pmt[1]}, ${pmt[2]:,.2f} on {pmt[3]}")
        issues.append(f"ORPHAN_REFUNDS: {len(orphan_refunds)} refunds without original payments")
else:
    print("   ✅ No negative payments found")

print()

# ============================================================================
# 7. CHARTER DATE CONSISTENCY CHECK
# ============================================================================
print("7. CHECKING CHARTER DATE CONSISTENCY...")
print("-" * 120)

pg_cur.execute("""
    SELECT COUNT(*)
    FROM charters
    WHERE charter_date IS NULL
""")
null_dates = pg_cur.fetchone()[0]

if null_dates > 0:
    print(f"   ⚠️  Found {null_dates} charters with NULL charter_date")
    issues.append(f"NULL_CHARTER_DATES: {null_dates} charters")
else:
    print("   ✅ All charters have charter_date")

# Check for future dates beyond reasonable booking window
pg_cur.execute("""
    SELECT COUNT(*)
    FROM charters
    WHERE charter_date > CURRENT_DATE + INTERVAL '2 years'
""")
far_future = pg_cur.fetchone()[0]

if far_future > 0:
    print(f"   ⚠️  Found {far_future} charters dated more than 2 years in future")
    issues.append(f"FAR_FUTURE_DATES: {far_future} charters")

# Check for very old dates (before company incorporation 2003)
pg_cur.execute("""
    SELECT COUNT(*)
    FROM charters
    WHERE charter_date < '2003-01-01'
""")
too_old = pg_cur.fetchone()[0]

if too_old > 0:
    print(f"   ⚠️  Found {too_old} charters dated before 2003 (company incorporation)")
    issues.append(f"PRE_2003_DATES: {too_old} charters")

print()

# ============================================================================
# 8. CLIENT LINKAGE CHECK
# ============================================================================
print("8. CHECKING CLIENT LINKAGE...")
print("-" * 120)

pg_cur.execute("""
    SELECT COUNT(*)
    FROM charters
    WHERE client_id IS NULL
""")
null_clients = pg_cur.fetchone()[0]

print(f"   ℹ️  {null_clients} charters have NULL client_id (expected for some old records)")

# Check for invalid client_id references
pg_cur.execute("""
    SELECT COUNT(*)
    FROM charters c
    WHERE c.client_id IS NOT NULL
      AND NOT EXISTS (SELECT 1 FROM clients cl WHERE cl.client_id = c.client_id)
""")
invalid_clients = pg_cur.fetchone()[0]

if invalid_clients > 0:
    print(f"   ⚠️  Found {invalid_clients} charters with INVALID client_id (client doesn't exist)")
    issues.append(f"INVALID_CLIENT_IDS: {invalid_clients} charters")
else:
    print("   ✅ All non-NULL client_ids are valid")

print()

# ============================================================================
# 9. PAYMENT KEY ANALYSIS
# ============================================================================
print("9. CHECKING PAYMENT KEY PATTERNS...")
print("-" * 120)

pg_cur.execute("""
    SELECT 
        CASE 
            WHEN payment_key LIKE 'LMS:%' THEN 'LMS'
            WHEN payment_key LIKE 'SQ:%' THEN 'Square'
            WHEN payment_key LIKE 'BTX:%' THEN 'Banking'
            WHEN payment_key LIKE 'LMSDEP:%' THEN 'LMS Deposit'
            WHEN payment_key ~ '^[0-9]{7}$' THEN 'Legacy 7-digit'
            WHEN payment_key IS NULL THEN 'NULL'
            ELSE 'Other'
        END as key_type,
        COUNT(*),
        SUM(amount)
    FROM payments
    GROUP BY key_type
    ORDER BY COUNT(*) DESC
""")
key_types = pg_cur.fetchall()

print("   Payment key type distribution:")
for key_type, count, total in key_types:
    print(f"      {key_type:<20} {count:>6} payments, ${total or 0:>12,.2f}")

print()

# ============================================================================
# SUMMARY
# ============================================================================
print()
print("=" * 120)
print("AUDIT SUMMARY")
print("=" * 120)

if issues:
    print(f"\n⚠️  FOUND {len(issues)} DATA INTEGRITY ISSUES:\n")
    for i, issue in enumerate(issues, 1):
        print(f"   {i}. {issue}")
    print()
    print("=" * 120)
    print("RECOMMENDED ACTIONS:")
    print("=" * 120)
    print("   1. Review duplicate payments and remove/merge as appropriate")
    print("   2. Recalculate all charter balances: python scripts/recalculate_charter_balances.py --write")
    print("   3. Investigate orphaned payments - may need charter linkage repair")
    print("   4. Sync charge totals with charter total_amount_due field")
    print("   5. Review and categorize unknown payment methods")
else:
    print("\n✅ NO DATA INTEGRITY ISSUES FOUND!")
    print("   Database appears to be in good condition.")

print()

pg_cur.close()
pg_conn.close()
