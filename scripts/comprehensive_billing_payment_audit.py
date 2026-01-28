#!/usr/bin/env python3
"""
In-depth Charter Billing & Payment Audit

Comprehensive analysis of:
1. Charter billing structure and amounts
2. Payment matching and linking
3. Balance analysis (billed vs paid)
4. Data integrity issues
5. Discrepancies and anomalies
"""

import psycopg2
import os
from datetime import datetime

conn = psycopg2.connect(
    host=os.getenv('DB_HOST', 'localhost'),
    dbname=os.getenv('DB_NAME', 'almsdata'),
    user=os.getenv('DB_USER', 'postgres'),
    password=os.getenv('DB_PASSWORD', '***REMOVED***'),
)
cur = conn.cursor()

print("\n" + "="*80)
print("COMPREHENSIVE CHARTER BILLING & PAYMENT AUDIT")
print("="*80)

# ============================================================================
# SECTION 1: CHARTER STRUCTURE & BILLING FIELDS
# ============================================================================
print("\n" + "-"*80)
print("1. CHARTER BILLING STRUCTURE")
print("-"*80)

cur.execute('''
    SELECT
        COUNT(*) AS total_charters,
        COUNT(CASE WHEN total_amount_due IS NOT NULL THEN 1 END) AS has_total_due,
        COUNT(CASE WHEN total_amount_due IS NOT NULL AND total_amount_due > 0 THEN 1 END) AS non_zero_due,
        COUNT(CASE WHEN total_amount_due = 0 THEN 1 END) AS zero_due,
        COUNT(CASE WHEN total_amount_due IS NULL THEN 1 END) AS null_due,
        ROUND(SUM(COALESCE(total_amount_due, 0))::numeric, 2) AS total_billing_amount,
        ROUND(AVG(COALESCE(total_amount_due, 0))::numeric, 2) AS avg_billing_amount
    FROM charters
''')

row = cur.fetchone()
print(f"\n📊 Charter Billing Overview:")
print(f"   Total Charters: {row[0]:,}")
print(f"   With total_amount_due: {row[1]:,} ({row[1]/row[0]*100:.1f}%)")
print(f"   Non-zero amounts: {row[2]:,}")
print(f"   Zero amount: {row[3]:,}")
print(f"   NULL amount: {row[4]:,}")
print(f"   Total Billed: ${row[5]:,.2f}")
print(f"   Average per Charter: ${row[6]:,.2f}")

# ============================================================================
# SECTION 2: PAYMENT STRUCTURE & LINKING
# ============================================================================
print("\n" + "-"*80)
print("2. PAYMENT STRUCTURE & LINKING")
print("-"*80)

cur.execute('''
    SELECT
        COUNT(*) AS total_payments,
        COUNT(CASE WHEN charter_id IS NOT NULL THEN 1 END) AS linked_to_charter,
        COUNT(CASE WHEN charter_id IS NULL THEN 1 END) AS unlinked,
        COUNT(CASE WHEN reserve_number IS NOT NULL THEN 1 END) AS has_reserve,
        COUNT(CASE WHEN payment_method IS NOT NULL THEN 1 END) AS has_method,
        COUNT(DISTINCT payment_method) AS method_count,
        ROUND(SUM(COALESCE(amount, 0))::numeric, 2) AS total_payments_amount,
        ROUND(AVG(COALESCE(amount, 0))::numeric, 2) AS avg_payment_amount
    FROM payments
''')

row = cur.fetchone()
print(f"\n💳 Payment Overview:")
print(f"   Total Payments: {row[0]:,}")
print(f"   Linked to charter: {row[1]:,} ({row[1]/row[0]*100:.1f}%)")
print(f"   Unlinked (orphaned): {row[2]:,} ({row[2]/row[0]*100:.1f}%)")
print(f"   With reserve_number: {row[3]:,}")
print(f"   With payment_method: {row[4]:,}")
print(f"   Payment Method Types: {row[5]}")
print(f"   Total Payments Amount: ${row[6]:,.2f}")
print(f"   Average per Payment: ${row[7]:,.2f}")

# ============================================================================
# SECTION 3: BALANCE ANALYSIS
# ============================================================================
print("\n" + "-"*80)
print("3. BALANCE ANALYSIS: BILLED vs PAID")
print("-"*80)

cur.execute('''
    WITH charter_payments AS (
        SELECT
            charter_id,
            SUM(COALESCE(amount, 0)) AS total_paid
        FROM payments
        WHERE reserve_number IS NOT NULL
        GROUP BY charter_id
    ),
    charter_with_balance AS (
        SELECT
            c.charter_id,
            c.reserve_number,
            COALESCE(c.total_amount_due, 0) AS amount_due,
            COALESCE(cp.total_paid, 0) AS amount_paid,
            COALESCE(c.total_amount_due, 0) - COALESCE(cp.total_paid, 0) AS balance,
            c.status
        FROM charters c
        LEFT JOIN charter_payments cp ON c.charter_id = cp.charter_id
    )
    SELECT
        COUNT(*) AS total,
        COUNT(CASE WHEN balance > 0 THEN 1 END) AS unpaid_count,
        COUNT(CASE WHEN balance < 0 THEN 1 END) AS overpaid_count,
        COUNT(CASE WHEN balance = 0 THEN 1 END) AS paid_in_full,
        ROUND(SUM(CASE WHEN balance > 0 THEN balance ELSE 0 END)::numeric, 2) AS total_unpaid,
        ROUND(SUM(CASE WHEN balance < 0 THEN ABS(balance) ELSE 0 END)::numeric, 2) AS total_overpaid,
        ROUND(SUM(CASE WHEN balance > 0 THEN balance ELSE 0 END)::numeric / 
              COUNT(CASE WHEN balance > 0 THEN 1 END), 2) AS avg_unpaid_per_charter,
        ROUND(SUM(CASE WHEN balance < 0 THEN ABS(balance) ELSE 0 END)::numeric / 
              COUNT(CASE WHEN balance < 0 THEN 1 END), 2) AS avg_overpaid_per_charter
    FROM charter_with_balance
''')

row = cur.fetchone()
print(f"\n💰 Balance Status:")
print(f"   Total Charters Analyzed: {row[0]:,}")
print(f"   Unpaid (balance > 0): {row[1]:,} ({row[1]/row[0]*100:.1f}%)")
print(f"   Overpaid (balance < 0): {row[2]:,} ({row[2]/row[0]*100:.1f}%)")
print(f"   Paid in Full (balance = 0): {row[3]:,}")
print(f"\n   Total Outstanding Balance (Unpaid): ${row[4]:,.2f}")
print(f"   Total Overpayment Amount: ${row[5]:,.2f}")
print(f"   Average Unpaid per Charter: ${row[6]:,.2f}")
print(f"   Average Overpaid per Charter: ${row[7]:,.2f}")

# ============================================================================
# SECTION 4: STATUS BREAKDOWN
# ============================================================================
print("\n" + "-"*80)
print("4. CHARTER STATUS BREAKDOWN")
print("-"*80)

cur.execute('''
    WITH charter_payments AS (
        SELECT
            charter_id,
            SUM(COALESCE(amount, 0)) AS total_paid
        FROM payments
        WHERE reserve_number IS NOT NULL
        GROUP BY charter_id
    ),
    charter_with_balance AS (
        SELECT
            c.charter_id,
            COALESCE(c.total_amount_due, 0) AS amount_due,
            COALESCE(cp.total_paid, 0) AS amount_paid,
            COALESCE(c.total_amount_due, 0) - COALESCE(cp.total_paid, 0) AS balance,
            c.status
        FROM charters c
        LEFT JOIN charter_payments cp ON c.charter_id = cp.charter_id
    )
    SELECT
        COALESCE(status, 'NULL') AS status,
        COUNT(*) AS count,
        ROUND(SUM(amount_due)::numeric, 2) AS total_billed,
        ROUND(SUM(amount_paid)::numeric, 2) AS total_paid,
        ROUND(SUM(balance)::numeric, 2) AS total_balance,
        COUNT(CASE WHEN balance > 0 THEN 1 END) AS unpaid_count,
        COUNT(CASE WHEN balance < 0 THEN 1 END) AS overpaid_count,
        COUNT(CASE WHEN balance = 0 THEN 1 END) AS balanced_count
    FROM charter_with_balance
    GROUP BY status
    ORDER BY count DESC
''')

print(f"\n📋 Status Breakdown:")
print(f"{'Status':<25} {'Count':>8} {'Billed':>15} {'Paid':>15} {'Balance':>15} {'Unpaid':>8} {'Overpaid':>9} {'Balanced':>8}")
print("-" * 100)

for row in cur.fetchall():
    status = row[0][:24]
    print(f"{status:<25} {row[1]:>8,} ${row[2]:>14,.2f} ${row[3]:>14,.2f} ${row[4]:>14,.2f} {row[5]:>8,} {row[6]:>9,} {row[7]:>8,}")

# ============================================================================
# SECTION 5: PAYMENT METHOD BREAKDOWN
# ============================================================================
print("\n" + "-"*80)
print("5. PAYMENT METHOD BREAKDOWN")
print("-"*80)

cur.execute('''
    SELECT
        COALESCE(payment_method, 'NULL') AS method,
        COUNT(*) AS payment_count,
        ROUND(SUM(COALESCE(amount, 0))::numeric, 2) AS total_amount,
        ROUND(AVG(COALESCE(amount, 0))::numeric, 2) AS avg_amount,
        COUNT(CASE WHEN charter_id IS NOT NULL THEN 1 END) AS linked_count,
        COUNT(CASE WHEN charter_id IS NULL THEN 1 END) AS unlinked_count
    FROM payments
    GROUP BY payment_method
    ORDER BY total_amount DESC
''')

print(f"\n{'Method':<20} {'Payments':>10} {'Total Amount':>18} {'Average':>15} {'Linked':>8} {'Unlinked':>9}")
print("-" * 90)

for row in cur.fetchall():
    method = row[0][:19]
    print(f"{method:<20} {row[1]:>10,} ${row[2]:>17,.2f} ${row[3]:>14,.2f} {row[4]:>8,} {row[5]:>9,}")

# ============================================================================
# SECTION 6: DATA INTEGRITY ISSUES
# ============================================================================
print("\n" + "-"*80)
print("6. DATA INTEGRITY ISSUES")
print("-"*80)

# Missing payment methods
cur.execute('''
    SELECT COUNT(*) FROM payments WHERE payment_method IS NULL
''')
null_methods = cur.fetchone()[0]
print(f"\n⚠️  Payments with NULL payment_method: {null_methods:,}")

# Missing charter links
cur.execute('''
    SELECT COUNT(*) FROM payments WHERE reserve_number IS NULL AND reserve_number IS NULL
''')
orphaned = cur.fetchone()[0]
print(f"⚠️  Payments with no charter_id AND no reserve_number: {orphaned:,}")

# Inconsistent reserve numbers
cur.execute('''
    SELECT COUNT(*) FROM payments p
    WHERE p.reserve_number IS NOT NULL
      AND NOT EXISTS (SELECT 1 FROM charters c WHERE c.reserve_number = p.reserve_number)
''')
invalid_reserves = cur.fetchone()[0]
print(f"⚠️  Payments with invalid reserve_number (not in charters): {invalid_reserves:,}")

# Charters with no billing amount
cur.execute('''
    SELECT COUNT(*) FROM charters WHERE total_amount_due IS NULL OR total_amount_due = 0
''')
no_billing = cur.fetchone()[0]
print(f"⚠️  Charters with NULL or $0 total_amount_due: {no_billing:,}")

# Negative amounts (should not exist)
cur.execute('''
    SELECT COUNT(*) FROM payments WHERE amount < 0
''')
negative = cur.fetchone()[0]
print(f"⚠️  Payments with negative amount: {negative:,}")

# ============================================================================
# SECTION 7: TOP DISCREPANCIES
# ============================================================================
print("\n" + "-"*80)
print("7. TOP DISCREPANCIES: OVERPAYMENTS & UNDERPAYMENTS")
print("-"*80)

print("\n📈 Top 10 OVERPAID Charters (paid more than billed):")
cur.execute('''
    WITH charter_payments AS (
        SELECT
            charter_id,
            SUM(COALESCE(amount, 0)) AS total_paid
        FROM payments
        WHERE reserve_number IS NOT NULL
        GROUP BY charter_id
    )
    SELECT
        c.charter_id,
        c.reserve_number,
        COALESCE(c.total_amount_due, 0) AS amount_due,
        COALESCE(cp.total_paid, 0) AS amount_paid,
        COALESCE(cp.total_paid, 0) - COALESCE(c.total_amount_due, 0) AS overpaid,
        c.status
    FROM charters c
    LEFT JOIN charter_payments cp ON c.charter_id = cp.charter_id
    WHERE COALESCE(cp.total_paid, 0) > COALESCE(c.total_amount_due, 0)
    ORDER BY overpaid DESC
    LIMIT 10
''')

rows = cur.fetchall()
if rows:
    print(f"{'Charter':>8} {'Reserve':>8} {'Billed':>12} {'Paid':>12} {'Overpaid':>12} {'Status':<20}")
    print("-" * 80)
    for row in rows:
        print(f"{row[0]:>8} {row[1]:>8} ${row[2]:>11,.2f} ${row[3]:>11,.2f} ${row[4]:>11,.2f} {row[5][:19]:<20}")
else:
    print("  (none)")

print("\n📉 Top 10 UNDERPAID Charters (owed the most):")
cur.execute('''
    WITH charter_payments AS (
        SELECT
            charter_id,
            SUM(COALESCE(amount, 0)) AS total_paid
        FROM payments
        WHERE reserve_number IS NOT NULL
        GROUP BY charter_id
    )
    SELECT
        c.charter_id,
        c.reserve_number,
        COALESCE(c.total_amount_due, 0) AS amount_due,
        COALESCE(cp.total_paid, 0) AS amount_paid,
        COALESCE(c.total_amount_due, 0) - COALESCE(cp.total_paid, 0) AS unpaid,
        c.status
    FROM charters c
    LEFT JOIN charter_payments cp ON c.charter_id = cp.charter_id
    WHERE COALESCE(c.total_amount_due, 0) > COALESCE(cp.total_paid, 0)
    ORDER BY unpaid DESC
    LIMIT 10
''')

rows = cur.fetchall()
if rows:
    print(f"{'Charter':>8} {'Reserve':>8} {'Billed':>12} {'Paid':>12} {'Unpaid':>12} {'Status':<20}")
    print("-" * 80)
    for row in rows:
        print(f"{row[0]:>8} {row[1]:>8} ${row[2]:>11,.2f} ${row[3]:>11,.2f} ${row[4]:>11,.2f} {row[5][:19]:<20}")
else:
    print("  (none)")

# ============================================================================
# SECTION 8: ZERO-BILLING CHARTERS WITH PAYMENTS
# ============================================================================
print("\n" + "-"*80)
print("8. ZERO-BILLING CHARTERS WITH PAYMENTS")
print("-"*80)

cur.execute('''
    WITH charter_payments AS (
        SELECT
            charter_id,
            SUM(COALESCE(amount, 0)) AS total_paid
        FROM payments
        WHERE reserve_number IS NOT NULL
        GROUP BY charter_id
    )
    SELECT
        COUNT(*) AS count,
        ROUND(SUM(cp.total_paid)::numeric, 2) AS total_paid,
        ROUND(AVG(cp.total_paid)::numeric, 2) AS avg_paid
    FROM charters c
    JOIN charter_payments cp ON c.charter_id = cp.charter_id
    WHERE COALESCE(c.total_amount_due, 0) = 0
      AND cp.total_paid > 0
''')

row = cur.fetchone()
print(f"\n⚠️  Charters with $0 billing but payments received:")
print(f"   Count: {row[0]:,}")
if row[1] is not None:
    print(f"   Total Paid: ${row[1]:,.2f}")
    print(f"   Average Paid: ${row[2]:,.2f}")
else:
    print(f"   Total Paid: $0.00")
    print(f"   Average Paid: $0.00")

# ============================================================================
# SECTION 9: PAYMENT DISTRIBUTION
# ============================================================================
print("\n" + "-"*80)
print("9. PAYMENT DISTRIBUTION BY DATE RANGE")
print("-"*80)

cur.execute('''
    SELECT
        EXTRACT(YEAR FROM payment_date)::int AS year,
        COUNT(*) AS payment_count,
        ROUND(SUM(COALESCE(amount, 0))::numeric, 2) AS total_paid,
        ROUND(AVG(COALESCE(amount, 0))::numeric, 2) AS avg_paid
    FROM payments
    WHERE payment_date IS NOT NULL
    GROUP BY EXTRACT(YEAR FROM payment_date)
    ORDER BY year DESC
    LIMIT 15
''')

print(f"\n{'Year':>6} {'Payments':>12} {'Total Amount':>18} {'Average':>15}")
print("-" * 55)
for row in cur.fetchall():
    print(f"{int(row[0]):>6} {row[1]:>12,} ${row[2]:>17,.2f} ${row[3]:>14,.2f}")

# ============================================================================
# SECTION 10: SUMMARY STATISTICS
# ============================================================================
print("\n" + "-"*80)
print("10. SUMMARY STATISTICS")
print("-"*80)

cur.execute('''
    WITH charter_payments AS (
        SELECT
            charter_id,
            SUM(COALESCE(amount, 0)) AS total_paid
        FROM payments
        WHERE reserve_number IS NOT NULL
        GROUP BY charter_id
    ),
    charter_with_balance AS (
        SELECT
            c.charter_id,
            COALESCE(c.total_amount_due, 0) AS amount_due,
            COALESCE(cp.total_paid, 0) AS amount_paid,
            COALESCE(c.total_amount_due, 0) - COALESCE(cp.total_paid, 0) AS balance
        FROM charters c
        LEFT JOIN charter_payments cp ON c.charter_id = cp.charter_id
    )
    SELECT
        ROUND((SUM(CASE WHEN balance = 0 THEN 1 ELSE 0 END)::numeric / COUNT(*)) * 100, 1) AS pct_fully_paid,
        ROUND((SUM(CASE WHEN balance > 0 THEN 1 ELSE 0 END)::numeric / COUNT(*)) * 100, 1) AS pct_unpaid,
        ROUND((SUM(CASE WHEN balance < 0 THEN 1 ELSE 0 END)::numeric / COUNT(*)) * 100, 1) AS pct_overpaid,
        ROUND((SUM(amount_due)::numeric / SUM(amount_paid)) * 100, 1) AS collection_rate
    FROM charter_with_balance
''')

row = cur.fetchone()
print(f"\n📊 Key Metrics:")
print(f"   Charters Fully Paid: {row[0]}%")
print(f"   Charters with Outstanding Balance: {row[1]}%")
print(f"   Charters Overpaid: {row[2]}%")
print(f"   Collection Rate (Paid/Billed): {row[3]}%")

print("\n" + "="*80 + "\n")

cur.close()
conn.close()
