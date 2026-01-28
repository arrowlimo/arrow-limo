#!/usr/bin/env python3
"""
Analyze outstanding receivables - SIMPLIFIED VERSION
Shows unpaid charters, amounts, ages, and patterns.
"""
import psycopg2
from datetime import datetime
import os

# Database connection
conn = psycopg2.connect(
    host=os.environ.get("DB_HOST", "localhost"),
    database=os.environ.get("DB_NAME", "almsdata"),
    user=os.environ.get("DB_USER", "postgres"),
    password=os.environ.get("DB_PASSWORD", "***REMOVED***")
)
cur = conn.cursor()

print("=" * 100)
print("OUTSTANDING RECEIVABLES ANALYSIS".center(100))
print("=" * 100)
print()

# Get base totals for context
cur.execute("""
    WITH charter_payments AS (
        SELECT 
            c.charter_id,
            c.total_amount_due,
            COALESCE(SUM(p.amount), 0) as total_paid
        FROM charters c
        LEFT JOIN payments p ON p.reserve_number = c.reserve_number
        GROUP BY c.charter_id, c.total_amount_due
    )
    SELECT 
        COUNT(*) as total_charters,
        SUM(CASE WHEN total_amount_due - total_paid > 0 THEN 1 ELSE 0 END) as unpaid_charters,
        SUM(CASE WHEN total_amount_due - total_paid > 0 THEN total_amount_due - total_paid ELSE 0 END) as total_outstanding
    FROM charter_payments
""")

total_charters, unpaid_charters, total_outstanding = cur.fetchone()

print(f"📊 OVERVIEW:")
print(f"  Total charters:           {total_charters:,}")
print(f"  Unpaid charters:          {unpaid_charters:,} ({unpaid_charters/total_charters*100:.1f}%)")
print(f"  Total outstanding:        ${total_outstanding:,.2f}")
print()

# 1. Distribution by amount owed
print("-" * 100)
print("1. OUTSTANDING BALANCE DISTRIBUTION")
print("-" * 100)
print()

cur.execute("""
    WITH charter_payments AS (
        SELECT 
            c.charter_id,
            c.total_amount_due,
            COALESCE(SUM(p.amount), 0) as total_paid,
            c.total_amount_due - COALESCE(SUM(p.amount), 0) as outstanding
        FROM charters c
        LEFT JOIN payments p ON p.reserve_number = c.reserve_number
        GROUP BY c.charter_id, c.total_amount_due
    )
    SELECT 
        COUNT(*) as count,
        SUM(outstanding) as total_owed,
        ROUND(AVG(outstanding)::numeric, 2) as avg_owed,
        MIN(outstanding) as min_owed,
        MAX(outstanding) as max_owed,
        SUM(outstanding) FILTER (WHERE outstanding >= 10000) as gte_10k,
        SUM(outstanding) FILTER (WHERE outstanding >= 5000 AND outstanding < 10000) as gte_5k,
        SUM(outstanding) FILTER (WHERE outstanding >= 2000 AND outstanding < 5000) as gte_2k,
        SUM(outstanding) FILTER (WHERE outstanding >= 1000 AND outstanding < 2000) as gte_1k,
        SUM(outstanding) FILTER (WHERE outstanding >= 500 AND outstanding < 1000) as gte_500,
        SUM(outstanding) FILTER (WHERE outstanding >= 100 AND outstanding < 500) as gte_100,
        SUM(outstanding) FILTER (WHERE outstanding > 0 AND outstanding < 100) as lt_100
    FROM charter_payments
    WHERE outstanding > 0
""")

count, total, avg, min_amt, max_amt, gte_10k, gte_5k, gte_2k, gte_1k, gte_500, gte_100, lt_100 = cur.fetchone()

print(f"Amount Ranges by Volume:")
print(f"  ≥$10,000            : {gte_10k:>12,.2f}" if gte_10k else f"  ≥$10,000            :            $0.00")
print(f"  $5,000-$10,000      : {gte_5k:>12,.2f}" if gte_5k else f"  $5,000-$10,000      :            $0.00")
print(f"  $2,000-$5,000       : {gte_2k:>12,.2f}" if gte_2k else f"  $2,000-$5,000       :            $0.00")
print(f"  $1,000-$2,000       : {gte_1k:>12,.2f}" if gte_1k else f"  $1,000-$2,000       :            $0.00")
print(f"  $500-$1,000         : {gte_500:>12,.2f}" if gte_500 else f"  $500-$1,000         :            $0.00")
print(f"  $100-$500           : {gte_100:>12,.2f}" if gte_100 else f"  $100-$500           :            $0.00")
print(f"  <$100               : {lt_100:>12,.2f}" if lt_100 else f"  <$100               :            $0.00")
print()
print(f"Statistics:")
print(f"  Total count:              {count:,} charters")
print(f"  Total amount:             ${total:,.2f}")
print(f"  Average per charter:      ${avg:,.2f}")
print(f"  Range:                    ${min_amt:,.2f} - ${max_amt:,.2f}")
print()

# 2. Distribution by charter age
print("-" * 100)
print("2. OUTSTANDING BY CHARTER AGE")
print("-" * 100)
print()

cur.execute("""
    WITH charter_payments AS (
        SELECT 
            c.charter_id,
            c.charter_date::date,
            c.total_amount_due,
            COALESCE(SUM(p.amount), 0) as total_paid,
            c.total_amount_due - COALESCE(SUM(p.amount), 0) as outstanding,
            (CURRENT_DATE::date - c.charter_date::date) as days_old
        FROM charters c
        LEFT JOIN payments p ON p.reserve_number = c.reserve_number
        GROUP BY c.charter_id, c.charter_date::date, c.total_amount_due
    )
    SELECT 
        COUNT(*) as count,
        SUM(outstanding) as total,
        ROUND(AVG(outstanding)::numeric, 2) as avg,
        MIN(days_old) as days_min,
        MAX(days_old) as days_max
    FROM charter_payments
    WHERE outstanding > 0
""")

count, total, avg, min_days, max_days = cur.fetchone()
print(f"All unpaid charters: {count:,} charters | ${total:,.2f} | Avg: ${avg:,.2f}")
print(f"Age range: {min_days}-{max_days} days old")
print()

# Age buckets
cur.execute("""
    WITH charter_payments AS (
        SELECT 
            c.charter_id,
            c.charter_date,
            c.total_amount_due,
            COALESCE(SUM(p.amount), 0) as total_paid,
            c.total_amount_due - COALESCE(SUM(p.amount), 0) as outstanding,
            EXTRACT(DAYS FROM CURRENT_DATE - c.charter_date)::int as days_old
        FROM charters c
        LEFT JOIN payments p ON p.reserve_number = c.reserve_number
        GROUP BY c.charter_id, c.charter_date, c.total_amount_due
    )
    SELECT 
        SUM(CASE WHEN days_old <= 30 THEN outstanding ELSE 0 END) as age_0_30,
        SUM(CASE WHEN days_old > 30 AND days_old <= 90 THEN outstanding ELSE 0 END) as age_31_90,
        SUM(CASE WHEN days_old > 90 AND days_old <= 180 THEN outstanding ELSE 0 END) as age_91_180,
        SUM(CASE WHEN days_old > 180 AND days_old <= 365 THEN outstanding ELSE 0 END) as age_181_365,
        SUM(CASE WHEN days_old > 365 AND days_old <= 730 THEN outstanding ELSE 0 END) as age_366_730,
        SUM(CASE WHEN days_old > 730 AND days_old <= 1095 THEN outstanding ELSE 0 END) as age_731_1095,
        SUM(CASE WHEN days_old > 1095 THEN outstanding ELSE 0 END) as age_1095_plus,
        COUNT(CASE WHEN days_old <= 30 THEN 1 END) as count_0_30,
        COUNT(CASE WHEN days_old > 30 AND days_old <= 90 THEN 1 END) as count_31_90,
        COUNT(CASE WHEN days_old > 90 AND days_old <= 180 THEN 1 END) as count_91_180,
        COUNT(CASE WHEN days_old > 180 AND days_old <= 365 THEN 1 END) as count_181_365,
        COUNT(CASE WHEN days_old > 365 AND days_old <= 730 THEN 1 END) as count_366_730,
        COUNT(CASE WHEN days_old > 730 AND days_old <= 1095 THEN 1 END) as count_731_1095,
        COUNT(CASE WHEN days_old > 1095 THEN 1 END) as count_1095_plus
    FROM charter_payments
    WHERE outstanding > 0
""")

a0_30, a31_90, a91_180, a181_365, a366_730, a731_1095, a1095plus, c0_30, c31_90, c91_180, c181_365, c366_730, c731_1095, c1095plus = cur.fetchone()

print(f"Age Breakdown:")
print(f"  0-30 days old       : {c0_30:>6} charters | ${a0_30:>12,.2f}")
print(f"  31-90 days old      : {c31_90:>6} charters | ${a31_90:>12,.2f}")
print(f"  91-180 days old     : {c91_180:>6} charters | ${a91_180:>12,.2f}")
print(f"  181-365 days old    : {c181_365:>6} charters | ${a181_365:>12,.2f}")
print(f"  ⚠️  1-2 years old      : {c366_730:>6} charters | ${a366_730:>12,.2f}")
print(f"  🔴 2-3 years old      : {c731_1095:>6} charters | ${a731_1095:>12,.2f}")
print(f"  🔥 3+ years old       : {c1095plus:>6} charters | ${a1095plus:>12,.2f}")
print()

# 3. Distribution by charter status
print("-" * 100)
print("3. OUTSTANDING BY CHARTER STATUS")
print("-" * 100)
print()

cur.execute("""
    WITH charter_payments AS (
        SELECT 
            c.charter_id,
            COALESCE(c.status, 'NULL') as status,
            c.total_amount_due,
            COALESCE(SUM(p.amount), 0) as total_paid,
            c.total_amount_due - COALESCE(SUM(p.amount), 0) as outstanding
        FROM charters c
        LEFT JOIN payments p ON p.reserve_number = c.reserve_number
        GROUP BY c.charter_id, c.status, c.total_amount_due
    )
    SELECT 
        status,
        COUNT(*) as count,
        SUM(outstanding) as total_owed,
        ROUND(AVG(outstanding)::numeric, 2) as avg_owed
    FROM charter_payments
    WHERE outstanding > 0
    ORDER BY total_owed DESC
""")

rows = cur.fetchall()
for status, count, owed, avg in rows:
    pct = (owed / total_outstanding * 100) if total_outstanding > 0 else 0
    print(f"  {status:30} | {count:6} charters | ${owed:12,.2f} ({pct:5.1f}%) | Avg: ${avg:8,.2f}")

print()

# 4. Top 20 outstanding receivables
print("-" * 100)
print("4. TOP 20 LARGEST OUTSTANDING RECEIVABLES")
print("-" * 100)
print()

cur.execute("""
    WITH charter_payments AS (
        SELECT 
            c.charter_id,
            c.reserve_number,
            c.charter_date,
            c.total_amount_due,
            c.status,
            c.customer_name,
            COALESCE(SUM(p.amount), 0) as total_paid,
            c.total_amount_due - COALESCE(SUM(p.amount), 0) as outstanding,
            EXTRACT(DAYS FROM CURRENT_DATE - c.charter_date)::int as days_old
        FROM charters c
        LEFT JOIN payments p ON p.reserve_number = c.reserve_number
        GROUP BY c.charter_id, c.reserve_number, c.charter_date, c.total_amount_due, c.status, c.customer_name
    )
    SELECT 
        charter_id,
        reserve_number,
        charter_date,
        days_old,
        total_amount_due,
        total_paid,
        outstanding,
        status,
        customer_name
    FROM charter_payments
    WHERE outstanding > 0
    ORDER BY outstanding DESC
    LIMIT 20
""")

rows = cur.fetchall()
print(f"{'Charter':7} {'Reserve':9} {'Charter Date':12} {'Days Old':8} {'Billed':11} {'Paid':11} {'Outstanding':12} {'Status':20}")
print("-" * 110)

for charter_id, reserve, charter_date, days_old, billed, paid, outstanding, status, customer in rows:
    status_str = (status or 'NULL')[:18]
    print(f"{charter_id:7} {reserve:9} {str(charter_date):12} {days_old:8} ${billed:10,.2f} ${paid:10,.2f} ${outstanding:11,.2f} {status_str:20}")

print()

# 5. Critical aging summary
print("-" * 100)
print("5. CRITICAL AGING SUMMARY - RECEIVABLES BY AGE URGENCY")
print("-" * 100)
print()

cur.execute("""
    WITH charter_payments AS (
        SELECT 
            c.charter_id,
            c.charter_date,
            c.total_amount_due,
            COALESCE(SUM(p.amount), 0) as total_paid,
            c.total_amount_due - COALESCE(SUM(p.amount), 0) as outstanding,
            EXTRACT(DAYS FROM CURRENT_DATE - c.charter_date)::int as days_old
        FROM charters c
        LEFT JOIN payments p ON p.reserve_number = c.reserve_number
        GROUP BY c.charter_id, c.charter_date, c.total_amount_due
    )
    SELECT 
        SUM(CASE WHEN days_old > 365 THEN outstanding ELSE 0 END) as over_1yr,
        SUM(CASE WHEN days_old > 730 THEN outstanding ELSE 0 END) as over_2yr,
        SUM(CASE WHEN days_old > 1095 THEN outstanding ELSE 0 END) as over_3yr,
        COUNT(CASE WHEN days_old > 365 THEN 1 END) as count_over_1yr,
        COUNT(CASE WHEN days_old > 730 THEN 1 END) as count_over_2yr,
        COUNT(CASE WHEN days_old > 1095 THEN 1 END) as count_over_3yr
    FROM charter_payments
    WHERE outstanding > 0
""")

over_1yr, over_2yr, over_3yr, count_1yr, count_2yr, count_3yr = cur.fetchone()

print(f"⚠️  OVER 1 YEAR OLD     : {count_1yr:,} charters | ${over_1yr:,.2f} ({over_1yr/total_outstanding*100:.1f}% of total)")
print(f"🔴 OVER 2 YEARS OLD    : {count_2yr:,} charters | ${over_2yr:,.2f} ({over_2yr/total_outstanding*100:.1f}% of total)")
print(f"🔥 OVER 3 YEARS OLD    : {count_3yr:,} charters | ${over_3yr:,.2f} ({over_3yr/total_outstanding*100:.1f}% of total)")
print()

# 6. Financial summary statistics
print("-" * 100)
print("6. FINANCIAL SUMMARY STATISTICS")
print("-" * 100)
print()

cur.execute("""
    WITH charter_payments AS (
        SELECT 
            c.charter_id,
            c.total_amount_due,
            COALESCE(SUM(p.amount), 0) as total_paid,
            c.total_amount_due - COALESCE(SUM(p.amount), 0) as outstanding
        FROM charters c
        LEFT JOIN payments p ON p.reserve_number = c.reserve_number
        GROUP BY c.charter_id, c.total_amount_due
    )
    SELECT 
        COUNT(*) as count,
        SUM(outstanding) as total,
        ROUND(AVG(outstanding)::numeric, 2) as avg,
        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY outstanding) as median,
        PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY outstanding) as pct_75,
        PERCENTILE_CONT(0.9) WITHIN GROUP (ORDER BY outstanding) as pct_90,
        PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY outstanding) as pct_95,
        MAX(outstanding) as max
    FROM charter_payments
    WHERE outstanding > 0
""")

count, total, avg, median, pct_75, pct_90, pct_95, max_amt = cur.fetchone()

print(f"  Total unpaid charters:     {count:,}")
print(f"  Total outstanding:         ${total:,.2f}")
print(f"  Average per charter:       ${avg:,.2f}")
print(f"  Median amount:             ${median:,.2f}")
print(f"  75th percentile:           ${pct_75:,.2f}")
print(f"  90th percentile:           ${pct_90:,.2f}")
print(f"  95th percentile:           ${pct_95:,.2f}")
print(f"  Maximum single:            ${max_amt:,.2f}")
print()

# 7. Payment methods for unpaid charters
print("-" * 100)
print("7. PAYMENT ACTIVITY ON UNPAID CHARTERS")
print("-" * 100)
print()

cur.execute("""
    WITH charter_payments AS (
        SELECT 
            c.charter_id,
            c.total_amount_due,
            COALESCE(SUM(p.amount), 0) as total_paid,
            c.total_amount_due - COALESCE(SUM(p.amount), 0) as outstanding
        FROM charters c
        LEFT JOIN payments p ON p.reserve_number = c.reserve_number
        GROUP BY c.charter_id, c.total_amount_due
    )
    SELECT 
        COUNT(*) as count
    FROM charter_payments
    WHERE outstanding > 0 AND total_paid = 0
""")

no_payment = cur.fetchone()[0]

cur.execute("""
    WITH charter_payments AS (
        SELECT 
            c.charter_id,
            c.total_amount_due,
            COALESCE(SUM(p.amount), 0) as total_paid,
            c.total_amount_due - COALESCE(SUM(p.amount), 0) as outstanding
        FROM charters c
        LEFT JOIN payments p ON p.reserve_number = c.reserve_number
        GROUP BY c.charter_id, c.total_amount_due
    )
    SELECT 
        COUNT(*) as count,
        SUM(total_paid) as total
    FROM charter_payments
    WHERE outstanding > 0 AND total_paid > 0
""")

with_payment_row = cur.fetchone()
with_payment_count, with_payment_total = with_payment_row if with_payment_row[0] else (0, 0)

print(f"  Charters with NO payment : {no_payment:,} ({no_payment/unpaid_charters*100:.1f}%)")
print(f"  Charters WITH payment    : {with_payment_count:,} ({with_payment_count/unpaid_charters*100:.1f}%) | Total paid: ${with_payment_total:,.2f}")
print()

print("=" * 100)

cur.close()
conn.close()
