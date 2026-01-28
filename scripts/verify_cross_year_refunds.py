#!/usr/bin/env python3
"""
Scan entire almsdata for cross-year refund issues.

Find charters where:
1. Charter date in year X
2. Payments include refunds (negative amounts) dated in year X+1 or later
3. paid_amount doesn't reflect the refund (balance mismatch)
"""
import psycopg2
import os
from collections import defaultdict

conn = psycopg2.connect(
    host=os.getenv('DB_HOST', 'localhost'),
    database=os.getenv('DB_NAME', 'almsdata'),
    user=os.getenv('DB_USER', 'postgres'),
    password=os.getenv('DB_PASSWORD', '***REMOVED***')
)
cur = conn.cursor()

print("="*80)
print("CROSS-YEAR REFUND AUDIT - ALL YEARS")
print("="*80)

# Find all charters with payments in different years
cur.execute("""
    WITH charter_payment_years AS (
        SELECT 
            c.reserve_number,
            c.charter_date,
            EXTRACT(YEAR FROM c.charter_date) as charter_year,
            COUNT(p.payment_id) as payment_count,
            COUNT(DISTINCT EXTRACT(YEAR FROM p.payment_date)) as payment_years,
            MIN(EXTRACT(YEAR FROM p.payment_date)) as min_payment_year,
            MAX(EXTRACT(YEAR FROM p.payment_date)) as max_payment_year,
            SUM(CASE WHEN p.amount < 0 THEN 1 ELSE 0 END) as refund_count,
            c.total_amount_due,
            c.paid_amount,
            c.balance
        FROM charters c
        JOIN payments p ON p.reserve_number = c.reserve_number
        WHERE c.reserve_number IS NOT NULL
        GROUP BY c.reserve_number, c.charter_date, c.total_amount_due, c.paid_amount, c.balance
    )
    SELECT 
        reserve_number,
        charter_date,
        charter_year,
        payment_count,
        payment_years,
        min_payment_year,
        max_payment_year,
        refund_count,
        total_amount_due,
        paid_amount,
        balance
    FROM charter_payment_years
    WHERE payment_years > 1
    OR (refund_count > 0 AND max_payment_year > charter_year)
    ORDER BY charter_year, reserve_number
""")

cross_year_charters = cur.fetchall()

print(f"\nFound {len(cross_year_charters)} charters with cross-year payments or refunds")

# Group by year
by_year = defaultdict(list)
for row in cross_year_charters:
    by_year[int(row[2])].append(row)

# Detailed analysis
issues_found = []

for charter_year in sorted(by_year.keys()):
    charters = by_year[charter_year]
    print(f"\n{'='*80}")
    print(f"CHARTER YEAR {charter_year} - {len(charters)} charters with cross-year payments")
    print(f"{'='*80}")
    
    for row in charters:
        reserve, cdate, cyear, pcount, pyears, minyear, maxyear, refunds, total_due, paid, bal = row
        
        # Calculate what paid_amount SHOULD be
        cur.execute("""
            SELECT COALESCE(SUM(amount), 0)
            FROM payments
            WHERE reserve_number = %s
        """, (reserve,))
        correct_paid = cur.fetchone()[0]
        
        # Check for mismatch
        paid_diff = abs(float(paid or 0) - float(correct_paid))
        balance_diff = abs(float(bal or 0) - (float(total_due or 0) - float(correct_paid)))
        
        has_issue = paid_diff > 0.01 or balance_diff > 0.01
        
        if has_issue:
            issues_found.append({
                'reserve': reserve,
                'charter_year': int(cyear),
                'charter_date': cdate,
                'payment_years': f"{int(minyear)}-{int(maxyear)}",
                'refunds': refunds,
                'total_due': float(total_due or 0),
                'current_paid': float(paid or 0),
                'correct_paid': float(correct_paid),
                'current_balance': float(bal or 0),
                'correct_balance': float(total_due or 0) - float(correct_paid),
                'paid_diff': paid_diff,
                'balance_diff': balance_diff
            })
        
        status = "[ISSUE]" if has_issue else "[OK]"
        print(f"{status} Rsv {reserve} | Charter: {cdate} | Payments: {int(pcount)} across {int(minyear)}-{int(maxyear)} | Refunds: {refunds}")
        if has_issue:
            print(f"       Paid: ${paid:.2f} should be ${correct_paid:.2f} (diff: ${paid_diff:.2f})")
            print(f"       Balance: ${bal:.2f} should be ${float(total_due or 0) - float(correct_paid):.2f} (diff: ${balance_diff:.2f})")

# Summary by year
print("\n" + "="*80)
print("SUMMARY BY CHARTER YEAR")
print("="*80)

year_summary = defaultdict(lambda: {'total': 0, 'issues': 0, 'refunds': 0})
for issue in issues_found:
    year = issue['charter_year']
    year_summary[year]['total'] = len(by_year[year])
    year_summary[year]['issues'] += 1
    if issue['refunds'] > 0:
        year_summary[year]['refunds'] += 1

for year in sorted(year_summary.keys()):
    info = year_summary[year]
    print(f"{year}: {info['issues']:3d} issues / {info['total']:3d} cross-year charters ({info['issues']/info['total']*100:5.1f}%) | {info['refunds']} with refunds")

# Overall summary
print("\n" + "="*80)
print("OVERALL SUMMARY")
print("="*80)
print(f"Total charters with cross-year payments: {len(cross_year_charters)}")
print(f"Charters with balance issues: {len(issues_found)}")
print(f"Issue rate: {len(issues_found)/len(cross_year_charters)*100:.1f}%" if cross_year_charters else "N/A")

# Show top issues
if issues_found:
    print("\n" + "="*80)
    print("TOP 20 ISSUES BY PAID AMOUNT DIFFERENCE")
    print("="*80)
    
    sorted_issues = sorted(issues_found, key=lambda x: x['paid_diff'], reverse=True)[:20]
    for i, issue in enumerate(sorted_issues, 1):
        print(f"{i:2d}. Rsv {issue['reserve']} | Year {issue['charter_year']} | "
              f"Paid diff: ${issue['paid_diff']:,.2f} | "
              f"Payment years: {issue['payment_years']} | "
              f"Refunds: {issue['refunds']}")

# Export list for fixing
if issues_found:
    print("\n" + "="*80)
    print("RESERVES NEEDING RECALCULATION")
    print("="*80)
    print("Run these commands to fix:")
    print()
    
    # Group by year for efficient batch processing
    by_charter_year = defaultdict(list)
    for issue in issues_found:
        by_charter_year[issue['charter_year']].append(issue['reserve'])
    
    for year in sorted(by_charter_year.keys()):
        reserves = by_charter_year[year]
        print(f"# {year} ({len(reserves)} charters)")
        print(f"# python scripts/recalculate_charter_balances.py --year {year} --write --backup")
        print(f"# Affected reserves: {', '.join(reserves[:10])}{'...' if len(reserves) > 10 else ''}")
        print()

cur.close()
conn.close()
