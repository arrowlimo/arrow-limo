#!/usr/bin/env python3
"""
COMPREHENSIVE PAYMENT SYSTEM ANALYSIS
Analyze every payment in the system after recalculation.
"""

import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REDACTED***'
)

cur = conn.cursor(cursor_factory=RealDictCursor)

print("=" * 80)
print("COMPREHENSIVE PAYMENT SYSTEM ANALYSIS")
print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 80)

# 1. OVERALL PAYMENT STATISTICS
print("\n" + "=" * 80)
print("1️⃣ OVERALL PAYMENT STATISTICS")
print("=" * 80)

cur.execute("""
    SELECT 
        COUNT(*) as total_payments,
        COUNT(charter_id) as linked_payments,
        COUNT(*) - COUNT(charter_id) as unlinked_payments,
        SUM(amount) as total_amount,
        SUM(CASE WHEN charter_id IS NOT NULL THEN amount ELSE 0 END) as linked_amount,
        SUM(CASE WHEN charter_id IS NULL THEN amount ELSE 0 END) as unlinked_amount,
        MIN(payment_date) as earliest_payment,
        MAX(payment_date) as latest_payment
    FROM payments
""")

overall = cur.fetchone()

print(f"\n📊 PAYMENT COUNTS:")
print(f"   Total payments: {overall['total_payments']:,}")
print(f"   Linked to charters: {overall['linked_payments']:,} ({overall['linked_payments']/overall['total_payments']*100:.1f}%)")
print(f"   Unlinked (orphaned): {overall['unlinked_payments']:,} ({overall['unlinked_payments']/overall['total_payments']*100:.1f}%)")

print(f"\n💰 PAYMENT AMOUNTS:")
print(f"   Total: ${overall['total_amount']:,.2f}")
print(f"   Linked: ${overall['linked_amount']:,.2f}")
print(f"   Unlinked: ${overall['unlinked_amount']:,.2f}")

print(f"\n📅 DATE RANGE:")
print(f"   Earliest: {overall['earliest_payment']}")
print(f"   Latest: {overall['latest_payment']}")

# 2. PAYMENTS ON CANCELLED CHARTERS
print("\n" + "=" * 80)
print("2️⃣ PAYMENTS ON CANCELLED CHARTERS")
print("=" * 80)

cur.execute("""
    SELECT 
        COUNT(DISTINCT p.charter_id) as cancelled_charters,
        COUNT(p.payment_id) as payment_count,
        SUM(p.amount) as total_amount
    FROM payments p
    JOIN charters c ON c.charter_id = p.charter_id
    WHERE c.cancelled = true
""")

cancelled = cur.fetchone()

print(f"\n📊 CANCELLED CHARTER PAYMENTS:")
print(f"   Charters: {cancelled['cancelled_charters'] or 0}")
print(f"   Payments: {cancelled['payment_count'] or 0}")
print(f"   Amount: ${cancelled['total_amount'] or 0:,.2f}")

if cancelled['payment_count'] and cancelled['payment_count'] > 0:
    print(f"\n   [WARN] WARNING: {cancelled['payment_count']} payments still on cancelled charters!")
else:
    print(f"\n   [OK] GOOD: No payments linked to cancelled charters")

# 3. ORPHANED PAYMENTS
print("\n" + "=" * 80)
print("3️⃣ ORPHANED PAYMENTS (NULL charter_id)")
print("=" * 80)

cur.execute("""
    SELECT 
        COUNT(*) as orphan_count,
        SUM(amount) as orphan_amount,
        COUNT(CASE WHEN reserve_number IS NOT NULL THEN 1 END) as with_reserve,
        COUNT(CASE WHEN reserve_number IS NULL THEN 1 END) as no_reserve
    FROM payments
    WHERE charter_id IS NULL
""")

orphans = cur.fetchone()

print(f"\n📊 ORPHANED PAYMENTS:")
print(f"   Total orphaned: {orphans['orphan_count']:,}")
print(f"   With reserve number: {orphans['with_reserve']:,}")
print(f"   Without reserve number: {orphans['no_reserve']:,}")
print(f"   Total amount: ${orphans['orphan_amount']:,.2f}")

# 4. CHARTER BALANCE ANALYSIS
print("\n" + "=" * 80)
print("4️⃣ CHARTER BALANCE ANALYSIS (ACTIVE CHARTERS)")
print("=" * 80)

cur.execute("""
    SELECT 
        COUNT(*) as total_charters,
        COUNT(CASE WHEN balance > 0.01 THEN 1 END) as owing_balance,
        COUNT(CASE WHEN balance < -0.01 THEN 1 END) as credit_balance,
        COUNT(CASE WHEN ABS(balance) <= 0.01 THEN 1 END) as zero_balance,
        SUM(CASE WHEN balance > 0.01 THEN balance ELSE 0 END) as total_owing,
        SUM(CASE WHEN balance < -0.01 THEN balance ELSE 0 END) as total_credits
    FROM charters
    WHERE cancelled = false
""")

balances = cur.fetchone()

print(f"\n📊 BALANCE DISTRIBUTION:")
print(f"   Total active charters: {balances['total_charters']:,}")
print(f"   Owing balance: {balances['owing_balance']:,} (${balances['total_owing']:,.2f})")
print(f"   Credit balance: {balances['credit_balance']:,} (${balances['total_credits']:,.2f})")
print(f"   Zero balance: {balances['zero_balance']:,}")

# 5. PAYMENT-CHARTER CONSISTENCY
print("\n" + "=" * 80)
print("5️⃣ PAYMENT-CHARTER CONSISTENCY CHECK")
print("=" * 80)

cur.execute("""
    WITH payment_sums AS (
        SELECT 
            reserve_number,
            COUNT(*) as payment_count,
            ROUND(SUM(COALESCE(amount, 0))::numeric, 2) as payment_sum
        FROM payments
        WHERE reserve_number IS NOT NULL
        GROUP BY reserve_number
    )
    SELECT 
        COUNT(*) as total_with_payments,
        COUNT(CASE WHEN ABS(COALESCE(c.paid_amount, 0) - COALESCE(ps.payment_sum, 0)) > 0.01 THEN 1 END) as mismatched
    FROM charters c
    JOIN payment_sums ps ON ps.reserve_number = c.reserve_number
""")

consistency = cur.fetchone()

print(f"\n📊 CONSISTENCY CHECK:")
print(f"   Charters with payments: {consistency['total_with_payments']:,}")
print(f"   Mismatched paid_amount: {consistency['mismatched'] or 0:,}")

if consistency['mismatched'] and consistency['mismatched'] > 0:
    print(f"\n   [WARN] WARNING: {consistency['mismatched']} charters have payment mismatch!")
else:
    print(f"\n   [OK] PERFECT: All charter.paid_amount matches payment sums!")

# 6. DUPLICATE DETECTION
print("\n" + "=" * 80)
print("6️⃣ POTENTIAL DUPLICATE DETECTION")
print("=" * 80)

cur.execute("""
    SELECT COUNT(*) as potential_duplicates
    FROM (
        SELECT charter_id, amount, payment_date, COUNT(*) as dup_count
        FROM payments
        WHERE charter_id IS NOT NULL
        GROUP BY charter_id, amount, payment_date
        HAVING COUNT(*) > 1
    ) dups
""")

dupes = cur.fetchone()

print(f"\n📊 DUPLICATE PATTERNS:")
print(f"   Potential duplicates: {dupes['potential_duplicates'] or 0:,}")

if dupes['potential_duplicates'] and dupes['potential_duplicates'] > 0:
    print(f"\n   [WARN] Found {dupes['potential_duplicates']} groups with same charter/amount/date")
else:
    print(f"\n   [OK] GOOD: No obvious duplicates detected")

# 7. PAYMENT METHOD DISTRIBUTION
print("\n" + "=" * 80)
print("7️⃣ PAYMENT METHOD DISTRIBUTION")
print("=" * 80)

cur.execute("""
    SELECT 
        payment_method,
        COUNT(*) as count,
        SUM(amount) as total
    FROM payments
    WHERE payment_method IS NOT NULL
    GROUP BY payment_method
    ORDER BY SUM(amount) DESC
""")

methods = cur.fetchall()

print(f"\n📊 PAYMENT METHODS:")
for m in methods:
    print(f"   {m['payment_method']:20s}: {m['count']:6,} payments  ${m['total']:14,.2f}")

# 8. CANCELLED CHARTER SUMMARY
print("\n" + "=" * 80)
print("8️⃣ CANCELLED CHARTER SUMMARY")
print("=" * 80)

cur.execute("""
    SELECT 
        COUNT(*) as cancelled_count,
        SUM(total_amount_due) as total_due,
        SUM(paid_amount) as total_paid,
        SUM(balance) as total_balance
    FROM charters
    WHERE cancelled = true
""")

cancelled_summary = cur.fetchone()

print(f"\n📊 CANCELLED CHARTERS:")
print(f"   Total cancelled: {cancelled_summary['cancelled_count']:,}")
print(f"   Total due: ${cancelled_summary['total_due'] or 0:,.2f}")
print(f"   Total paid: ${cancelled_summary['total_paid'] or 0:,.2f}")
print(f"   Total balance: ${cancelled_summary['total_balance'] or 0:,.2f}")

# 9. CHARTER 019404 SPECIFIC CHECK
print("\n" + "=" * 80)
print("9️⃣ CHARTER 019404 STATUS CHECK")
print("=" * 80)

cur.execute("""
    SELECT charter_id, reserve_number, total_amount_due, paid_amount, balance, cancelled
    FROM charters
    WHERE reserve_number = '019404'
""")

charter_019404 = cur.fetchone()

if charter_019404:
    print(f"\n📊 CHARTER 019404:")
    print(f"   Total due: ${charter_019404['total_amount_due'] or 0:.2f}")
    print(f"   Paid: ${charter_019404['paid_amount'] or 0:.2f}")
    print(f"   Balance: ${charter_019404['balance'] or 0:.2f}")
    print(f"   Cancelled: {charter_019404['cancelled']}")
    
    cur.execute("""
        SELECT COUNT(*) as cnt, SUM(amount) as total
        FROM payments
        WHERE reserve_number = '019404'
    """)
    payments_019404 = cur.fetchone()
    print(f"   Payments: {payments_019404['cnt']} totaling ${payments_019404['total'] or 0:.2f}")
    
    if charter_019404['cancelled'] and abs(charter_019404['balance'] or 0) < 0.01:
        print(f"\n   [OK] FIXED: Cancelled charter with zero balance")
    elif charter_019404['cancelled']:
        print(f"\n   [WARN] ISSUE: Cancelled charter still has non-zero balance")

print("\n" + "=" * 80)
print("✓ ANALYSIS COMPLETE")
print("=" * 80)

cur.close()
conn.close()
