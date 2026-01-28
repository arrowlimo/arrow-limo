#!/usr/bin/env python3
"""
Analyze why payments with reserve_number aren't matching to banking
"""

import psycopg2
from decimal import Decimal

DB_HOST = "localhost"
DB_NAME = "almsdata"
DB_USER = "postgres"
DB_PASSWORD = "***REMOVED***"

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

print("\n" + "="*70)
print("ANALYZING UNMATCHED PAYMENTS WITH RESERVE_NUMBER")
print("="*70)

# 1. How many payments have reserve_number?
cur.execute("""
    SELECT 
        COUNT(*) as total_payments,
        COUNT(CASE WHEN reserve_number IS NOT NULL THEN 1 END) as with_reserve,
        COUNT(CASE WHEN reserve_number IS NOT NULL AND banking_transaction_id IS NULL THEN 1 END) as with_reserve_unmatched,
        COUNT(CASE WHEN reserve_number IS NOT NULL AND banking_transaction_id IS NOT NULL THEN 1 END) as with_reserve_matched
    FROM payments
""")
total, with_res, unmatched, matched = cur.fetchone()
print(f"\n📊 Payment reserve_number coverage:")
print(f"   Total payments: {total:,}")
print(f"   With reserve_number: {with_res:,} ({with_res/total*100:.1f}%)")
print(f"   Unmatched (with reserve): {unmatched:,} ({unmatched/with_res*100:.1f}% of those with reserve)")
print(f"   Matched (with reserve): {matched:,} ({matched/with_res*100:.1f}% of those with reserve)")

# 2. How many charters have banking deposits?
cur.execute("""
    SELECT 
        COUNT(DISTINCT c.reserve_number) as charters_with_banking
    FROM charters c
    INNER JOIN banking_transactions b ON 
        b.credit_amount > 0 
        AND b.credit_amount > 0
        AND b.transaction_date BETWEEN c.charter_date - INTERVAL '10 days' AND c.charter_date + INTERVAL '30 days'
        AND ABS(c.total_amount_due - b.credit_amount) <= 5.00
    WHERE c.reserve_number IS NOT NULL
""")
charters_banking = cur.fetchone()[0]
print(f"\n💰 Charters with potential banking deposits:")
print(f"   {charters_banking:,} charters have banking matches within ±10-30 days, ±$5.00")

# 3. Why aren't more payments matching?
# Check payments with reserve_number but no banking match
cur.execute("""
    SELECT 
        p.reserve_number,
        COUNT(*) as payment_count,
        SUM(p.amount) as total_payments,
        MIN(p.payment_date) as earliest_payment,
        MAX(p.payment_date) as latest_payment,
        c.charter_date,
        c.total_amount_due,
        CASE 
            WHEN c.reserve_number IS NULL THEN 'No charter'
            WHEN c.charter_date IS NULL THEN 'Charter no date'
            ELSE 'Charter exists'
        END as charter_status
    FROM payments p
    LEFT JOIN charters c ON c.reserve_number = p.reserve_number
    WHERE p.reserve_number IS NOT NULL
    AND p.banking_transaction_id IS NULL
    GROUP BY p.reserve_number, c.charter_date, c.total_amount_due
    ORDER BY total_payments DESC
    LIMIT 10
""")

print(f"\n🔍 Top 10 unmatched reserve_numbers (by payment amount):")
print(f"{'Reserve':<10} {'Pmts':<6} {'Amount':<12} {'Pay Dates':<22} {'Charter Date':<14} {'Charter $':<12} {'Status':<20}")
print("-" * 130)
for row in cur.fetchall():
    res, cnt, amt, min_dt, max_dt, charter_dt, charter_amt, status = row
    min_str = min_dt.strftime("%Y-%m-%d") if min_dt else "None"
    max_str = max_dt.strftime("%Y-%m-%d") if max_dt else "None"
    charter_str = charter_dt.strftime("%Y-%m-%d") if charter_dt else "None"
    charter_amt_str = f"${charter_amt:,.2f}" if charter_amt else "N/A"
    print(f"{res:<10} {cnt:<6} ${amt:>10,.2f} {min_str} to {max_str:<10} {charter_str:<14} {charter_amt_str:<12} {status:<20}")

# 4. Check if banking deposits exist for these charters
cur.execute("""
    SELECT 
        p.reserve_number,
        COUNT(DISTINCT b.transaction_id) as banking_deposits,
        SUM(b.credit_amount) as total_deposits
    FROM payments p
    LEFT JOIN charters c ON c.reserve_number = p.reserve_number
    LEFT JOIN banking_transactions b ON 
        b.credit_amount > 0
        AND b.transaction_date BETWEEN c.charter_date - INTERVAL '10 days' AND c.charter_date + INTERVAL '30 days'
    WHERE p.reserve_number IS NOT NULL
    AND p.banking_transaction_id IS NULL
    GROUP BY p.reserve_number
    HAVING COUNT(DISTINCT b.transaction_id) > 0
    ORDER BY total_deposits DESC NULLS LAST
    LIMIT 10
""")

print(f"\n💸 Unmatched reserve_numbers WITH banking deposits:")
print(f"{'Reserve':<10} {'Banking Deposits':<18} {'Total Deposit $':<18}")
print("-" * 50)
for row in cur.fetchall():
    res, dep_cnt, dep_amt = row
    print(f"{res:<10} {dep_cnt:<18} ${dep_amt:>15,.2f}" if dep_amt else f"{res:<10} {dep_cnt:<18} N/A")

cur.close()
conn.close()

print("\n" + "="*70)
