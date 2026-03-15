#!/usr/bin/env python3
"""
Analyze outstanding receivables in detail.
Shows unpaid charters, amounts, ages, and patterns.
"""
import psycopg2
from datetime import datetime, timedelta
import os

# Database connection
conn = psycopg2.connect(
    host=os.environ.get("DB_HOST", "localhost"),
    database=os.environ.get("DB_NAME", "almsdata"),
    user=os.environ.get("DB_USER", "postgres"),
    password=os.environ.get("DB_PASSWORD", "***REDACTED***")
)
cur = conn.cursor()

print("=" * 90)
print("OUTSTANDING RECEIVABLES ANALYSIS")
print("=" * 90)
print()

# Calculate how old these charters are
today = datetime.now()

# 1. Distribution by amount owed
print("-" * 90)
print("1. OUTSTANDING BALANCE DISTRIBUTION")
print("-" * 90)
print()

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
        CASE 
            WHEN (total_amount_due - total_paid) >= 10000 THEN '≥$10,000'
            WHEN (total_amount_due - total_paid) >= 5000 THEN '$5,000-$10,000'
            WHEN (total_amount_due - total_paid) >= 2000 THEN '$2,000-$5,000'
            WHEN (total_amount_due - total_paid) >= 1000 THEN '$1,000-$2,000'
            WHEN (total_amount_due - total_paid) >= 500 THEN '$500-$1,000'
            WHEN (total_amount_due - total_paid) >= 100 THEN '$100-$500'
            WHEN (total_amount_due - total_paid) > 0 THEN '$0.01-$100'
        END as amount_range,
        COUNT(*) as count,
        SUM(total_amount_due - total_paid) as total_owed,
        ROUND(AVG(total_amount_due - total_paid)::numeric, 2) as avg_owed,
        MIN(total_amount_due - total_paid) as min_owed,
        MAX(total_amount_due - total_paid) as max_owed
    FROM charter_payments
    WHERE (total_amount_due - total_paid) > 0
    GROUP BY amount_range
    ORDER BY 
        CASE 
            WHEN amount_range = '≥$10,000' THEN 1
            WHEN amount_range = '$5,000-$10,000' THEN 2
            WHEN amount_range = '$2,000-$5,000' THEN 3
            WHEN amount_range = '$1,000-$2,000' THEN 4
            WHEN amount_range = '$500-$1,000' THEN 5
            WHEN amount_range = '$100-$500' THEN 6
            WHEN amount_range = '$0.01-$100' THEN 7
        END
""")

rows = cur.fetchall()
total_owed = 0
total_charters = 0

for range_label, count, owed, avg, min_amt, max_amt in rows:
    total_owed += owed
    total_charters += count
    print(f"{range_label:20} | {count:6} charters | ${owed:12,.2f} | Avg: ${avg:8,.2f} | Min: ${min_amt:8,.2f} | Max: ${max_amt:8,.2f}")

print()
print(f"{'TOTAL':20} | {total_charters:6} charters | ${total_owed:12,.2f}")
print()

# 2. Distribution by charter age
print("-" * 90)
print("2. OUTSTANDING BY CHARTER AGE (How long have these been unpaid?)")
print("-" * 90)
print()

cur.execute("""
    WITH charter_payments AS (
        SELECT 
            c.charter_id,
            c.charter_date,
            c.total_amount_due,
            COALESCE(SUM(p.amount), 0) as total_paid
        FROM charters c
        LEFT JOIN payments p ON p.reserve_number = c.reserve_number
        GROUP BY c.charter_id, c.charter_date, c.total_amount_due
    )
    SELECT 
        CASE 
            WHEN charter_date >= CURRENT_DATE - INTERVAL '30 days' THEN '0-30 days old'
            WHEN charter_date >= CURRENT_DATE - INTERVAL '90 days' THEN '31-90 days old'
            WHEN charter_date >= CURRENT_DATE - INTERVAL '180 days' THEN '91-180 days old'
            WHEN charter_date >= CURRENT_DATE - INTERVAL '1 year' THEN '181 days - 1 year old'
            WHEN charter_date >= CURRENT_DATE - INTERVAL '2 years' THEN '1-2 years old'
            WHEN charter_date >= CURRENT_DATE - INTERVAL '3 years' THEN '2-3 years old'
            WHEN charter_date >= CURRENT_DATE - INTERVAL '5 years' THEN '3-5 years old'
            ELSE '5+ years old'
        END as age_range,
        COUNT(*) as count,
        SUM(total_amount_due - total_paid) as total_owed,
        ROUND(AVG(total_amount_due - total_paid)::numeric, 2) as avg_owed,
        MIN(EXTRACT(DAYS FROM CURRENT_DATE - charter_date)::int) as days_unpaid_min,
        MAX(EXTRACT(DAYS FROM CURRENT_DATE - charter_date)::int) as days_unpaid_max
    FROM charter_payments
    WHERE (total_amount_due - total_paid) > 0
    GROUP BY age_range
    ORDER BY 
        CASE 
            WHEN age_range = '0-30 days old' THEN 1
            WHEN age_range = '31-90 days old' THEN 2
            WHEN age_range = '91-180 days old' THEN 3
            WHEN age_range = '181 days - 1 year old' THEN 4
            WHEN age_range = '1-2 years old' THEN 5
            WHEN age_range = '2-3 years old' THEN 6
            WHEN age_range = '3-5 years old' THEN 7
            ELSE 8
        END
""")

rows = cur.fetchall()

for age_range, count, owed, avg, min_days, max_days in rows:
    print(f"{age_range:25} | {count:6} charters | ${owed:12,.2f} | Avg: ${avg:8,.2f} | Age: {min_days}-{max_days} days")

print()

# 3. Distribution by charter status
print("-" * 90)
print("3. OUTSTANDING BY CHARTER STATUS")
print("-" * 90)
print()

cur.execute("""
    WITH charter_payments AS (
        SELECT 
            c.charter_id,
            c.status,
            c.total_amount_due,
            COALESCE(SUM(p.amount), 0) as total_paid
        FROM charters c
        LEFT JOIN payments p ON p.reserve_number = c.reserve_number
        GROUP BY c.charter_id, c.status, c.total_amount_due
    )
    SELECT 
        COALESCE(status, 'NULL') as status,
        COUNT(*) as count,
        SUM(total_amount_due - total_paid) as total_owed,
        ROUND(AVG(total_amount_due - total_paid)::numeric, 2) as avg_owed
    FROM charter_payments
    WHERE (total_amount_due - total_paid) > 0
    GROUP BY status
    ORDER BY total_owed DESC
""")

rows = cur.fetchall()

for status, count, owed, avg in rows:
    pct = (owed / total_owed * 100) if total_owed > 0 else 0
    print(f"{status:30} | {count:6} charters | ${owed:12,.2f} ({pct:5.1f}%) | Avg: ${avg:8,.2f}")

print()

# 4. Top 30 outstanding receivables
print("-" * 90)
print("4. TOP 30 LARGEST OUTSTANDING RECEIVABLES")
print("-" * 90)
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
            COALESCE(SUM(p.amount), 0) as total_paid
        FROM charters c
        LEFT JOIN payments p ON p.reserve_number = c.reserve_number
        GROUP BY c.charter_id, c.reserve_number, c.charter_date, c.total_amount_due, c.status, c.customer_name
    )
    SELECT 
        charter_id,
        reserve_number,
        charter_date,
        EXTRACT(DAYS FROM CURRENT_DATE - charter_date)::int as days_unpaid,
        total_amount_due,
        total_paid,
        (total_amount_due - total_paid) as outstanding,
        status,
        customer_name
    FROM charter_payments
    WHERE (total_amount_due - total_paid) > 0
    ORDER BY outstanding DESC
    LIMIT 30
""")

rows = cur.fetchall()

print(f"{'Charter':7} {'Reserve':8} {'Charter Date':12} {'Days Old':8} {'Billed':10} {'Paid':10} {'Outstanding':12} {'Status':20} {'Customer'}")
print("-" * 120)

for charter_id, reserve, charter_date, days_old, billed, paid, outstanding, status, customer in rows:
    status_str = (status or 'NULL')[:18]
    customer_str = (customer or 'UNKNOWN')[:25]
    print(f"{charter_id:7} {reserve:8} {str(charter_date):12} {days_old:8} ${billed:9,.2f} ${paid:9,.2f} ${outstanding:11,.2f} {status_str:20} {customer_str}")

print()

# 5. Summary statistics
print("-" * 90)
print("5. SUMMARY STATISTICS")
print("-" * 90)
print()

cur.execute("""
    WITH charter_payments AS (
        SELECT 
            c.charter_id,
            c.charter_date,
            c.total_amount_due,
            COALESCE(SUM(p.amount), 0) as total_paid
        FROM charters c
        LEFT JOIN payments p ON p.reserve_number = c.reserve_number
        GROUP BY c.charter_id, c.charter_date, c.total_amount_due
    )
    SELECT 
        COUNT(*) as total_unpaid_charters,
        SUM(total_amount_due - total_paid) as total_outstanding,
        ROUND(AVG(total_amount_due - total_paid)::numeric, 2) as avg_outstanding,
        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY total_amount_due - total_paid) as median_outstanding,
        PERCENTILE_CONT(0.9) WITHIN GROUP (ORDER BY total_amount_due - total_paid) as percentile_90,
        PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY total_amount_due - total_paid) as percentile_95,
        MAX(total_amount_due - total_paid) as max_outstanding,
        MIN(EXTRACT(DAYS FROM CURRENT_DATE - charter_date)::int) as days_unpaid_oldest_recent,
        MAX(EXTRACT(DAYS FROM CURRENT_DATE - charter_date)::int) as days_unpaid_oldest
    FROM charter_payments
    WHERE (total_amount_due - total_paid) > 0
""")

row = cur.fetchone()
total_charters, total_outstanding, avg_outstanding, median_outstanding, pct_90, pct_95, max_outstanding, days_oldest_recent, days_oldest = row

print(f"Total unpaid charters:        {total_charters:,}")
print(f"Total outstanding amount:     ${total_outstanding:,.2f}")
print(f"Average outstanding per charter: ${avg_outstanding:,.2f}")
print(f"Median outstanding:           ${median_outstanding:,.2f}")
print(f"90th percentile:              ${pct_90:,.2f}")
print(f"95th percentile:              ${pct_95:,.2f}")
print(f"Largest single outstanding:   ${max_outstanding:,.2f}")
print()
print(f"Oldest unpaid charter:        {days_oldest} days old")
print(f"Most recent unpaid charter:   {days_oldest_recent} days old")
print()

# 6. Age analysis - how much is critically old?
print("-" * 90)
print("6. CRITICAL AGE BREAKDOWN")
print("-" * 90)
print()

cur.execute("""
    WITH charter_payments AS (
        SELECT 
            c.charter_id,
            c.charter_date,
            c.total_amount_due,
            COALESCE(SUM(p.amount), 0) as total_paid
        FROM charters c
        LEFT JOIN payments p ON p.reserve_number = c.reserve_number
        GROUP BY c.charter_id, c.charter_date, c.total_amount_due
    )
    SELECT 
        COUNT(*) as count,
        SUM(total_amount_due - total_paid) as total,
        ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM charter_payments WHERE total_amount_due - total_paid > 0), 1) as pct_charters,
        ROUND(100.0 * SUM(total_amount_due - total_paid) / (SELECT SUM(total_amount_due - total_paid) FROM charter_payments WHERE total_amount_due - total_paid > 0), 1) as pct_amount
    FROM charter_payments
    WHERE (total_amount_due - total_paid) > 0 AND charter_date < CURRENT_DATE - INTERVAL '1 year'
""")

row = cur.fetchone()
count_1yr, total_1yr, pct_charters_1yr, pct_amount_1yr = row
print(f"⚠️  OVER 1 YEAR OLD (365+ days): {count_1yr:,} charters | ${total_1yr:,.2f} ({pct_charters_1yr}% of charters, {pct_amount_1yr}% of amount)")

cur.execute("""
    WITH charter_payments AS (
        SELECT 
            c.charter_id,
            c.charter_date,
            c.total_amount_due,
            COALESCE(SUM(p.amount), 0) as total_paid
        FROM charters c
        LEFT JOIN payments p ON p.reserve_number = c.reserve_number
        GROUP BY c.charter_id, c.charter_date, c.total_amount_due
    )
    SELECT 
        COUNT(*) as count,
        SUM(total_amount_due - total_paid) as total,
        ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM charter_payments WHERE total_amount_due - total_paid > 0), 1) as pct_charters,
        ROUND(100.0 * SUM(total_amount_due - total_paid) / (SELECT SUM(total_amount_due - total_paid) FROM charter_payments WHERE total_amount_due - total_paid > 0), 1) as pct_amount
    FROM charter_payments
    WHERE (total_amount_due - total_paid) > 0 AND charter_date < CURRENT_DATE - INTERVAL '2 years'
""")

row = cur.fetchone()
count_2yr, total_2yr, pct_charters_2yr, pct_amount_2yr = row
print(f"🔴 OVER 2 YEARS OLD (730+ days): {count_2yr:,} charters | ${total_2yr:,.2f} ({pct_charters_2yr}% of charters, {pct_amount_2yr}% of amount)")

cur.execute("""
    WITH charter_payments AS (
        SELECT 
            c.charter_id,
            c.charter_date,
            c.total_amount_due,
            COALESCE(SUM(p.amount), 0) as total_paid
        FROM charters c
        LEFT JOIN payments p ON p.reserve_number = c.reserve_number
        GROUP BY c.charter_id, c.charter_date, c.total_amount_due
    )
    SELECT 
        COUNT(*) as count,
        SUM(total_amount_due - total_paid) as total,
        ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM charter_payments WHERE total_amount_due - total_paid > 0), 1) as pct_charters,
        ROUND(100.0 * SUM(total_amount_due - total_paid) / (SELECT SUM(total_amount_due - total_paid) FROM charter_payments WHERE total_amount_due - total_paid > 0), 1) as pct_amount
    FROM charter_payments
    WHERE (total_amount_due - total_paid) > 0 AND charter_date < CURRENT_DATE - INTERVAL '3 years'
""")

row = cur.fetchone()
count_3yr, total_3yr, pct_charters_3yr, pct_amount_3yr = row
print(f"🔥 OVER 3 YEARS OLD (1095+ days): {count_3yr:,} charters | ${total_3yr:,.2f} ({pct_charters_3yr}% of charters, {pct_amount_3yr}% of amount)")

print()

# 7. Payment status of unpaid charters
print("-" * 90)
print("7. PAYMENT METHODS OF UNPAID CHARTERS")
print("-" * 90)
print()

cur.execute("""
    WITH charter_payments AS (
        SELECT 
            c.charter_id,
            c.total_amount_due,
            COALESCE(SUM(p.amount), 0) as total_paid
        FROM charters c
        LEFT JOIN payments p ON p.reserve_number = c.reserve_number
        GROUP BY c.charter_id, c.total_amount_due
    ),
    unpaid_charters AS (
        SELECT charter_id FROM charter_payments WHERE total_amount_due - total_paid > 0
    )
    SELECT 
        p.payment_method,
        COUNT(DISTINCT c.charter_id) as charters_with_payments,
        COUNT(p.payment_id) as num_payments,
        SUM(p.amount) as total_paid_via_method
    FROM unpaid_charters uc
    JOIN charters c ON c.charter_id = uc.charter_id
    LEFT JOIN payments p ON p.reserve_number = c.reserve_number
    GROUP BY p.payment_method
    ORDER BY COUNT(p.payment_id) DESC
""")

rows = cur.fetchall()

for method, charters_with_payments, num_payments, total_paid, still_unpaid in rows:
    method_str = method or 'NULL/No payments'
    if num_payments and num_payments > 0:
        avg_payment = total_paid / num_payments if total_paid else 0
        print(f"{method_str:20} | {charters_with_payments:6} charters received payment | {num_payments:6} payments | ${total_paid:12,.2f} avg ${avg_payment:8,.2f}/payment")
    else:
        print(f"{method_str:20} | {charters_with_payments:6} charters - NO PAYMENTS RECEIVED")

print()
print("=" * 90)

cur.close()
conn.close()
