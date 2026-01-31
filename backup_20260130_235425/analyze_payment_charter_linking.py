#!/usr/bin/env python3
"""
Deep-dive analysis of payment-charter linking issue.

The audit revealed that 99.3% of payments are NOT linked to charter_id.
This script investigates why and what the correct linking strategy should be.
"""

import psycopg2
import os

conn = psycopg2.connect(
    host=os.getenv('DB_HOST', 'localhost'),
    dbname=os.getenv('DB_NAME', 'almsdata'),
    user=os.getenv('DB_USER', 'postgres'),
    password=os.getenv('DB_PASSWORD', '***REDACTED***'),
)
cur = conn.cursor()

print("\n" + "="*80)
print("DEEP-DIVE: PAYMENT-CHARTER LINKING ANALYSIS")
print("="*80)

# ============================================================================
# SECTION 1: LINKING STRATEGY COMPARISON
# ============================================================================
print("\n" + "-"*80)
print("1. LINKING STRATEGIES")
print("-"*80)

print("\n📊 Current State (charter_id linking):")
cur.execute('''
    WITH charter_payments AS (
        SELECT
            charter_id,
            reserve_number,
            COUNT(*) AS payment_count,
            SUM(COALESCE(amount, 0)) AS total_amount
        FROM payments
        WHERE reserve_number IS NOT NULL
        GROUP BY charter_id, reserve_number
    )
    SELECT
        COUNT(*) AS linked_charters,
        SUM(payment_count) AS total_payments,
        ROUND(SUM(total_amount)::numeric, 2) AS total_amount,
        ROUND(AVG(total_amount)::numeric, 2) AS avg_per_charter
    FROM charter_payments
''')

row = cur.fetchone()
print(f"   Charters with charter_id links: {row[0]:,}")
print(f"   Payments linked: {row[1]:,}")
print(f"   Total amount: ${row[2]:,.2f}")
print(f"   Average per charter: ${row[3]:,.2f}")

print("\n📊 Alternative: reserve_number linking:")
cur.execute('''
    WITH charter_by_reserve AS (
        SELECT DISTINCT reserve_number FROM charters
    ),
    payment_by_reserve AS (
        SELECT
            reserve_number,
            COUNT(*) AS payment_count,
            SUM(COALESCE(amount, 0)) AS total_amount
        FROM payments
        WHERE reserve_number IS NOT NULL
        GROUP BY reserve_number
    )
    SELECT
        COUNT(DISTINCT p.reserve_number) AS matched_reserves,
        SUM(p.payment_count) AS total_payments,
        ROUND(SUM(p.total_amount)::numeric, 2) AS total_amount,
        ROUND(AVG(p.total_amount)::numeric, 2) AS avg_per_reserve
    FROM payment_by_reserve p
    WHERE EXISTS (SELECT 1 FROM charter_by_reserve c WHERE c.reserve_number = p.reserve_number)
''')

row = cur.fetchone()
print(f"   Reserves with payments: {row[0]:,}")
print(f"   Payments by reserve_number: {row[1]:,}")
print(f"   Total amount: ${row[2]:,.2f}")
print(f"   Average per reserve: ${row[3]:,.2f}")

# ============================================================================
# SECTION 2: CHARTER_ID LINKING ANALYSIS
# ============================================================================
print("\n" + "-"*80)
print("2. CHARTER_ID LINKING QUALITY")
print("-"*80)

print("\n⚠️  Payments linked by charter_id:")
cur.execute('''
    SELECT
        COUNT(*) AS total_linked,
        COUNT(CASE WHEN reserve_number IS NOT NULL THEN 1 END) AS have_reserve,
        COUNT(CASE WHEN reserve_number IS NULL THEN 1 END) AS missing_reserve,
        COUNT(DISTINCT charter_id) AS unique_charters
    FROM payments
    WHERE reserve_number IS NOT NULL
''')

row = cur.fetchone()
print(f"   Total payments with charter_id: {row[0]:,}")
print(f"   Have reserve_number: {row[1]:,}")
print(f"   Missing reserve_number: {row[2]:,}")
print(f"   Unique charters: {row[3]:,}")

print("\n   Sample of linked payments:")
cur.execute('''
    SELECT
        p.payment_id,
        p.charter_id,
        p.reserve_number,
        p.amount,
        c.reserve_number AS charter_reserve,
        c.total_amount_due,
        CASE WHEN p.reserve_number = c.reserve_number THEN 'MATCH' ELSE 'MISMATCH' END AS status
    FROM payments p
    LEFT JOIN charters c ON c.charter_id = p.charter_id
    WHERE p.reserve_number IS NOT NULL
    LIMIT 10
''')

print(f"   {'Payment':>10} {'Charter':>10} {'Pay Res':>10} {'Amount':>12} {'Ch Res':>10} {'Due':>12} {'Status':<10}")
print("   " + "-"*80)

for row in cur.fetchall():
    status = row[6] if row[6] else "NO CHARTER"
    pay_res = str(row[2]) if row[2] else "NULL"
    ch_res = str(row[4]) if row[4] else "NULL"
    ch_due = row[5] if row[5] is not None else 0
    print(f"   {row[0]:>10} {row[1]:>10} {pay_res:>10} ${row[3]:>11,.2f} {ch_res:>10} ${ch_due:>11,.2f} {status:<10}")

# ============================================================================
# SECTION 3: RESERVE_NUMBER LINKING ANALYSIS
# ============================================================================
print("\n" + "-"*80)
print("3. RESERVE_NUMBER LINKING QUALITY")
print("-"*80)

cur.execute('''
    SELECT
        COUNT(*) AS total_with_reserve,
        COUNT(CASE WHEN charter_id IS NOT NULL THEN 1 END) AS also_has_charter_id,
        COUNT(CASE WHEN charter_id IS NULL THEN 1 END) AS no_charter_id,
        COUNT(DISTINCT reserve_number) AS unique_reserves
    FROM payments
    WHERE reserve_number IS NOT NULL
''')

row = cur.fetchone()
print(f"\n💰 Payments with reserve_number:")
print(f"   Total: {row[0]:,}")
print(f"   Also have charter_id: {row[1]:,}")
print(f"   No charter_id (orphaned): {row[2]:,}")
print(f"   Unique reserves: {row[3]:,}")

# Which reserves match charters?
cur.execute('''
    WITH payment_reserves AS (
        SELECT DISTINCT reserve_number FROM payments WHERE reserve_number IS NOT NULL
    ),
    charter_reserves AS (
        SELECT DISTINCT reserve_number FROM charters
    )
    SELECT
        (SELECT COUNT(*) FROM payment_reserves) AS payment_reserves,
        (SELECT COUNT(*) FROM charter_reserves) AS charter_reserves,
        (SELECT COUNT(*) FROM payment_reserves WHERE reserve_number IN (SELECT reserve_number FROM charter_reserves)) AS matching_reserves,
        (SELECT COUNT(*) FROM payment_reserves WHERE reserve_number NOT IN (SELECT reserve_number FROM charter_reserves)) AS non_matching_reserves
''')

row = cur.fetchone()
print(f"\n📌 Reserve_number matching status:")
print(f"   Payment reserve_numbers: {row[0]:,}")
print(f"   Charter reserve_numbers: {row[1]:,}")
print(f"   Matching: {row[2]:,} ({row[2]/row[0]*100:.1f}%)")
print(f"   Non-matching: {row[3]:,} ({row[3]/row[0]*100:.1f}%)")

# ============================================================================
# SECTION 4: UNLINKED PAYMENTS ANALYSIS
# ============================================================================
print("\n" + "-"*80)
print("4. UNLINKED PAYMENTS ANALYSIS")
print("-"*80)

cur.execute('''
    SELECT
        COUNT(*) AS total_unlinked,
        ROUND(SUM(COALESCE(amount, 0))::numeric, 2) AS total_amount,
        COUNT(CASE WHEN payment_method = 'unknown' THEN 1 END) AS unknown_method,
        COUNT(CASE WHEN payment_method = 'credit_card' THEN 1 END) AS credit_card,
        COUNT(DISTINCT EXTRACT(YEAR FROM payment_date)) AS year_range
    FROM payments
    WHERE reserve_number IS NULL
''')

row = cur.fetchone()
print(f"\n🚫 Payments NOT linked to charter_id:")
print(f"   Total: {row[0]:,}")
print(f"   Total Amount: ${row[1]:,.2f}")
print(f"   Unknown method: {row[2]:,}")
print(f"   Credit card: {row[3]:,}")
print(f"   Date range: {row[4]} years")

print("\n   Payment methods distribution (unlinked):")
cur.execute('''
    SELECT
        COALESCE(payment_method, 'NULL') AS method,
        COUNT(*) AS count,
        ROUND(SUM(COALESCE(amount, 0))::numeric, 2) AS total,
        ROUND(AVG(COALESCE(amount, 0))::numeric, 2) AS avg
    FROM payments
    WHERE reserve_number IS NULL
    GROUP BY payment_method
    ORDER BY count DESC
''')

for row in cur.fetchall():
    print(f"      {row[0]:<20} {row[1]:>10,} payments, ${row[2]:>15,.2f} total, ${row[3]:>12,.2f} avg")

# ============================================================================
# SECTION 5: RESERVE_NUMBER MISMATCH ANALYSIS
# ============================================================================
print("\n" + "-"*80)
print("5. RESERVE_NUMBER MISMATCH ANALYSIS")
print("-"*80)

cur.execute('''
    WITH charter_by_reserve AS (
        SELECT
            reserve_number,
            charter_id,
            total_amount_due,
            status
        FROM charters
    ),
    payment_by_reserve AS (
        SELECT
            reserve_number,
            COUNT(*) AS payment_count,
            SUM(COALESCE(amount, 0)) AS payment_total
        FROM payments
        WHERE reserve_number IS NOT NULL
        GROUP BY reserve_number
    )
    SELECT
        COUNT(*) AS reserves_with_payments,
        SUM(payment_count) AS total_payments,
        ROUND(SUM(payment_total)::numeric, 2) AS total_amount,
        COUNT(CASE WHEN p.payment_total > c.total_amount_due THEN 1 END) AS overpaid,
        COUNT(CASE WHEN p.payment_total < c.total_amount_due THEN 1 END) AS underpaid,
        COUNT(CASE WHEN p.payment_total = c.total_amount_due THEN 1 END) AS exact_match
    FROM payment_by_reserve p
    LEFT JOIN charter_by_reserve c ON p.reserve_number = c.reserve_number
''')

row = cur.fetchone()
print(f"\n🔗 Reserve-to-Charter Balance Matching:")
print(f"   Reserves with payments: {row[0]:,}")
print(f"   Total payments: {row[1]:,}")
print(f"   Total amount: ${row[2]:,.2f}")
print(f"   Overpaid reserves: {row[3]:,}")
print(f"   Underpaid reserves: {row[4]:,}")
print(f"   Exact matches: {row[5]:,}")

# ============================================================================
# SECTION 6: PROBLEM IDENTIFICATION
# ============================================================================
print("\n" + "-"*80)
print("6. ROOT CAUSE ANALYSIS")
print("-"*80)

print("\n🔍 Why are 99.3% of payments unlinked?")

# Check if payments_charter_id column is being used
cur.execute('''
    SELECT
        COUNT(CASE WHEN charter_id IS NOT NULL THEN 1 END) AS has_fk,
        COUNT(CASE WHEN charter_id IS NULL THEN 1 END) AS no_fk,
        COUNT(*) AS total
    FROM payments
''')

row = cur.fetchone()
print(f"\n   charter_id column status:")
print(f"   - Populated: {row[0]:,} ({row[0]/row[2]*100:.1f}%)")
print(f"   - NULL: {row[1]:,} ({row[1]/row[2]*100:.1f}%)")

print(f"\n💡 Root Cause Hypothesis:")
print(f"   Payments appear to be imported with reserve_number, NOT charter_id")
print(f"   The payments table has a FOREIGN KEY to charter_id but it's not being populated")
print(f"   Reserve_number is the actual business key used for matching")

print(f"\n✅ Solution:")
print(f"   1. Use reserve_number (not charter_id) to link payments to charters")
print(f"   2. Backfill charter_id from the reserve_number join")
print(f"   3. Or keep reserve_number as the linking key")

print("\n" + "="*80 + "\n")

cur.close()
conn.close()
