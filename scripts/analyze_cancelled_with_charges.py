#!/usr/bin/env python
"""
Identify charters that are marked cancelled but still have charges recorded.
Criteria:
  - Charter has cancelled=TRUE OR status contains 'cancel'
  - Charter has total_amount_due > 0 OR charter_charges rows exist
  - Charter date is BEFORE 2025-10-01 (exclude recent bookings)
Outputs:
  - Summary counts
  - Year breakdown
  - CSV export with full details
"""
import psycopg2
import csv
import os
from collections import defaultdict
from decimal import Decimal

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()

print('='*100)
print('Cancelled Charters with Charges Still Recorded (Pre-October 2025)')
print('='*100)

# Find cancelled charters with charges, excluding post-Oct 2025
cur.execute("""
    SELECT DISTINCT
        c.reserve_number,
        c.charter_date,
        c.account_number,
        c.status,
        c.cancelled,
        c.total_amount_due,
        c.paid_amount,
        c.balance,
        COUNT(cc.charge_id) as charge_count,
        COALESCE(SUM(cc.amount), 0) as total_charges
    FROM charters c
    LEFT JOIN charter_charges cc ON cc.reserve_number = c.reserve_number
    WHERE (c.cancelled = TRUE OR c.status ILIKE '%cancel%')
      AND c.charter_date < '2025-10-01'
      AND (c.total_amount_due > 0 OR EXISTS (
          SELECT 1 FROM charter_charges WHERE reserve_number = c.reserve_number
      ))
    GROUP BY c.reserve_number, c.charter_date, c.account_number, c.status, 
             c.cancelled, c.total_amount_due, c.paid_amount, c.balance
    ORDER BY c.charter_date DESC
""")
rows = cur.fetchall()

if not rows:
    print('No cancelled charters with charges found (pre-Oct 2025).')
    cur.close()
    conn.close()
    exit(0)

print(f"\nTotal cancelled charters with charges: {len(rows):,}")

# Year breakdown
year_counts = defaultdict(int)
for r in rows:
    _, charter_date, *_ = r
    if charter_date:
        year_counts[charter_date.year] += 1
    else:
        year_counts['(no date)'] += 1

print('\nBy Year:')
for y in sorted(year_counts, key=lambda k: (9999 if k=='(no date)' else k), reverse=True):
    print(f"  {y}: {year_counts[y]}")

# Top 50 by total charges
print('\nTop 50 by charges amount (descending):')
sorted_by_charges = sorted(rows, key=lambda r: r[9], reverse=True)
for r in sorted_by_charges[:50]:
    reserve_number, charter_date, account_number, status, cancelled, total_amount_due, paid_amount, balance, charge_count, total_charges = r
    print(f"  {reserve_number} date={charter_date} status={status} cancelled={cancelled} charges=${total_charges} count={charge_count}")

# Aggregate totals
total_charges_sum = sum(r[9] for r in rows)
total_due_sum = sum((r[5] or 0) for r in rows)
print(f"\nAggregate:")
print(f"  Total charges (from charter_charges): ${Decimal(total_charges_sum):,.2f}")
print(f"  Total amount due (from charters): ${Decimal(total_due_sum):,.2f}")

# Export CSV
os.makedirs('reports', exist_ok=True)
outfile = 'reports/cancelled_charters_with_charges.csv'
with open(outfile, 'w', newline='', encoding='utf-8') as f:
    w = csv.writer(f)
    w.writerow(['Reserve Number', 'Charter Date', 'Account Number', 'Status', 'Cancelled', 
                'Total Amount Due', 'Paid Amount', 'Balance', 'Charge Count', 'Total Charges'])
    for r in rows:
        w.writerow(r)

print(f"\nCSV exported: {outfile}")

cur.close()
conn.close()
print('\nDone.')
