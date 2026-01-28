#!/usr/bin/env python3
"""
Audit charters with uncollectible balances.
Identify old/cancelled charters where balance should be written off.
"""

import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timedelta

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REMOVED***'
)

cur = conn.cursor(cursor_factory=RealDictCursor)

print("=" * 80)
print("AUDIT: UNCOLLECTIBLE CHARTER BALANCES")
print("=" * 80)

# 1. Active charters with balances owing
print("\n" + "=" * 80)
print("1️⃣ ACTIVE CHARTERS WITH BALANCES OWING")
print("=" * 80)

cur.execute("""
    SELECT 
        reserve_number,
        charter_date,
        total_amount_due,
        paid_amount,
        balance,
        client_id,
        EXTRACT(YEAR FROM charter_date) as year
    FROM charters
    WHERE cancelled = false
    AND balance > 0.01
    ORDER BY charter_date
""")

active_owing = cur.fetchall()

print(f"\n📊 TOTAL: {len(active_owing)} charters owing ${sum(c['balance'] for c in active_owing):,.2f}")

# Group by year
by_year = {}
for c in active_owing:
    year = int(c['year'])
    if year not in by_year:
        by_year[year] = {'count': 0, 'total': 0}
    by_year[year]['count'] += 1
    by_year[year]['total'] += c['balance']

print(f"\n📅 BY YEAR:")
for year in sorted(by_year.keys()):
    print(f"   {year}: {by_year[year]['count']:3} charters, ${by_year[year]['total']:,.2f} owing")

# 2. Old charters (pre-2020) likely uncollectible
print("\n" + "=" * 80)
print("2️⃣ OLD CHARTERS (PRE-2020) - LIKELY UNCOLLECTIBLE")
print("=" * 80)

cur.execute("""
    SELECT 
        reserve_number,
        charter_date,
        total_amount_due,
        paid_amount,
        balance,
        EXTRACT(YEAR FROM NOW()) - EXTRACT(YEAR FROM charter_date) as years_old
    FROM charters
    WHERE cancelled = false
    AND balance > 0.01
    AND charter_date < '2020-01-01'
    ORDER BY balance DESC
""")

old_uncollectible = cur.fetchall()

print(f"\n📊 {len(old_uncollectible)} charters from pre-2020")
print(f"   Total owing: ${sum(c['balance'] for c in old_uncollectible):,.2f}")

if len(old_uncollectible) > 0:
    print(f"\n📋 TOP 20 OLD UNCOLLECTIBLE:")
    print(f"{'Reserve':<10} {'Date':<12} {'Total Due':<12} {'Paid':<12} {'Owing':<12} {'Years':<6}")
    print("-" * 80)
    
    for c in old_uncollectible[:20]:
        print(f"{c['reserve_number']:<10} {str(c['charter_date']):<12} "
              f"${c['total_amount_due']:>10,.2f} ${c['paid_amount']:>10,.2f} "
              f"${c['balance']:>10,.2f} {c['years_old']:>5}")

# 3. Charters with partial payment (paid something but not all)
print("\n" + "=" * 80)
print("3️⃣ PARTIAL PAYMENT CHARTERS")
print("=" * 80)

cur.execute("""
    SELECT 
        reserve_number,
        charter_date,
        total_amount_due,
        paid_amount,
        balance,
        ROUND((paid_amount / NULLIF(total_amount_due, 0) * 100)::numeric, 1) as percent_paid
    FROM charters
    WHERE cancelled = false
    AND balance > 0.01
    AND paid_amount > 0
    ORDER BY charter_date
""")

partial_payments = cur.fetchall()

print(f"\n📊 {len(partial_payments)} charters with partial payment")
print(f"   Total paid: ${sum(c['paid_amount'] for c in partial_payments):,.2f}")
print(f"   Still owing: ${sum(c['balance'] for c in partial_payments):,.2f}")

# Group by percent paid
ranges = {
    '90-99%': (90, 100),
    '75-89%': (75, 90),
    '50-74%': (50, 75),
    '25-49%': (25, 50),
    '1-24%': (1, 25)
}

print(f"\n📊 BY PERCENT PAID:")
for label, (min_pct, max_pct) in ranges.items():
    charters = [c for c in partial_payments if min_pct <= c['percent_paid'] < max_pct]
    if charters:
        total_owing = sum(c['balance'] for c in charters)
        print(f"   {label}: {len(charters):3} charters, ${total_owing:,.2f} owing")

# 4. Suggest write-off candidates
print("\n" + "=" * 80)
print("4️⃣ WRITE-OFF CANDIDATES (Pre-2020 + >90% paid)")
print("=" * 80)

cur.execute("""
    SELECT 
        reserve_number,
        charter_date,
        total_amount_due,
        paid_amount,
        balance,
        ROUND((paid_amount / NULLIF(total_amount_due, 0) * 100)::numeric, 1) as percent_paid
    FROM charters
    WHERE cancelled = false
    AND balance > 0.01
    AND (
        charter_date < '2020-01-01'
        OR (paid_amount / NULLIF(total_amount_due, 0)) >= 0.90
    )
    ORDER BY charter_date
""")

writeoff_candidates = cur.fetchall()

print(f"\n📊 {len(writeoff_candidates)} write-off candidates")
print(f"   Total to write off: ${sum(c['balance'] for c in writeoff_candidates):,.2f}")

if len(writeoff_candidates) > 0:
    print(f"\n💡 RECOMMENDATION:")
    print(f"   Reduce total_amount_due to match paid_amount")
    print(f"   This will:")
    print(f"     - Set balance to $0")
    print(f"     - Reduce revenue (and GST liability) by ${sum(c['balance'] for c in writeoff_candidates):,.2f}")
    print(f"     - Not affect gratuity already paid to drivers")

# 5. Show sample adjustment
if len(writeoff_candidates) > 0:
    print(f"\n" + "=" * 80)
    print("5️⃣ SAMPLE ADJUSTMENTS (TOP 10)")
    print("=" * 80)
    
    print(f"\n{'Reserve':<10} {'Current Total':<15} {'Paid':<15} {'New Total':<15} {'Adjustment':<12}")
    print("-" * 80)
    
    for c in writeoff_candidates[:10]:
        new_total = c['paid_amount']
        adjustment = c['total_amount_due'] - new_total
        print(f"{c['reserve_number']:<10} ${c['total_amount_due']:>13,.2f} "
              f"${c['paid_amount']:>13,.2f} ${new_total:>13,.2f} "
              f"${adjustment:>10,.2f}")

print("\n" + "=" * 80)
print("✓ Audit complete")
print("=" * 80)

cur.close()
conn.close()
