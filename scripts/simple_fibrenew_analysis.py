#!/usr/bin/env python3
"""Simple Fibrenew analysis - database receipts only."""

import psycopg2
from collections import defaultdict

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REMOVED***'
)
cur = conn.cursor()

print("="*120)
print("FIBRENEW RENT ANALYSIS - ALL PAYMENTS")
print("="*120)

# Get all Fibrenew receipts
cur.execute("""
    SELECT receipt_id, receipt_date, vendor_name, gross_amount, category, 
           gl_account_code, description
    FROM receipts
    WHERE vendor_name ILIKE '%fibrenew%' 
       OR description ILIKE '%fibrenew%'
       OR (category = 'rent' AND vendor_name ILIKE '%office rent%')
    ORDER BY receipt_date
""")

receipts = cur.fetchall()
print(f"\nTotal receipts found: {len(receipts)}")

# Group by year and month
by_year = defaultdict(lambda: {'count': 0, 'amount': 0})
by_month = defaultdict(lambda: {'count': 0, 'amount': 0, 'receipts': []})

for r in receipts:
    year = r[1].year
    month = f"{r[1].year}-{r[1].month:02d}"
    
    by_year[year]['count'] += 1
    by_year[year]['amount'] += r[3]
    
    by_month[month]['count'] += 1
    by_month[month]['amount'] += r[3]
    by_month[month]['receipts'].append(r)

# Year summary
print("\n" + "="*120)
print("YEARLY SUMMARY")
print("="*120)
print(f"{'Year':6s} | Count | Total Amount")
print("-"*120)
total_all = 0
for year in sorted(by_year.keys()):
    data = by_year[year]
    print(f"{year:6d} | {data['count']:5d} | ${data['amount']:>12,.2f}")
    total_all += data['amount']
print("-"*120)
print(f"{'TOTAL':6s} | {sum(d['count'] for d in by_year.values()):5d} | ${total_all:>12,.2f}")

# Monthly detail for last 24 months
print("\n" + "="*120)
print("MONTHLY DETAIL (Last 24 months)")
print("="*120)
print(f"{'Month':10s} | Count | Total Amount | Receipts")
print("-"*120)

months_sorted = sorted(by_month.keys(), reverse=True)[:24]
for month in months_sorted:
    data = by_month[month]
    print(f"{month:10s} | {data['count']:5d} | ${data['amount']:>11,.2f} |", end="")
    if data['count'] <= 3:
        amounts = [f"${r[3]:.2f}" for r in data['receipts']]
        print(f" {', '.join(amounts)}")
    else:
        print(f" {data['count']} payments")

# Check for duplicates (same date and amount)
print("\n" + "="*120)
print("POTENTIAL DUPLICATE CHECK")
print("="*120)

duplicates = defaultdict(list)
for r in receipts:
    key = (r[1], r[3])  # date + amount
    duplicates[key].append(r)

dup_count = sum(1 for dups in duplicates.values() if len(dups) > 1)
if dup_count > 0:
    print(f"\nFound {dup_count} potential duplicate groups:")
    for key, dups in sorted(duplicates.items()):
        if len(dups) > 1:
            print(f"\n{key[0]} | ${key[1]:.2f} - {len(dups)} receipts:")
            for r in dups:
                print(f"  ID {r[0]:6d} | {r[2]:30s} | {r[6][:50]}")
else:
    print("\n✅ No duplicate date+amount combinations found")

# Check for months with split payments
print("\n" + "="*120)
print("SPLIT PAYMENT PATTERNS (Multiple payments per month)")
print("="*120)

for month in sorted(by_month.keys(), reverse=True)[:12]:
    data = by_month[month]
    if data['count'] > 1:
        print(f"\n{month}: {data['count']} payments totaling ${data['amount']:.2f}")
        for r in data['receipts']:
            print(f"  {r[1]} | ${r[3]:>8.2f} | {r[2]:25s} | {r[6][:40]}")

# Summary statistics
print("\n" + "="*120)
print("PAYMENT STATISTICS")
print("="*120)

cur.execute("""
    SELECT 
        COUNT(*) as total_payments,
        SUM(gross_amount) as total_amount,
        AVG(gross_amount) as avg_payment,
        MIN(gross_amount) as min_payment,
        MAX(gross_amount) as max_payment,
        MIN(receipt_date) as first_payment,
        MAX(receipt_date) as last_payment
    FROM receipts
    WHERE vendor_name ILIKE '%fibrenew%' 
       OR description ILIKE '%fibrenew%'
       OR (category = 'rent' AND vendor_name ILIKE '%office rent%')
""")

stats = cur.fetchone()
print(f"\nTotal Payments: {stats[0]:,}")
print(f"Total Amount: ${stats[1]:,.2f}")
print(f"Average Payment: ${stats[2]:,.2f}")
print(f"Min Payment: ${stats[3]:,.2f}")
print(f"Max Payment: ${stats[4]:,.2f}")
print(f"Date Range: {stats[5]} to {stats[6]}")
print(f"Duration: {(stats[6] - stats[5]).days / 365.25:.1f} years")

conn.close()
