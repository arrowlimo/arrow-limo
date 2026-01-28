#!/usr/bin/env python
"""
Find charters with paid_amount > 0 but no payment linkages.
Pattern: charters.paid_amount > 0 but:
  - No charter_payments rows linking to this charter
  - No payments.reserve_number matching this charter
This indicates orphaned paid_amount that needs investigation.
"""
import psycopg2
import csv
import os

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

print('='*100)
print('Charters with ORPHANED paid_amount (no payment linkages)')
print('='*100)

# Find charters with paid_amount but no payment links
cur.execute("""
    SELECT c.reserve_number,
           c.charter_date,
           c.account_number,
           c.status,
           c.cancelled,
           c.total_amount_due,
           c.paid_amount,
           c.balance,
           (SELECT COUNT(*) FROM charter_payments WHERE charter_id = c.reserve_number) as cp_count,
           (SELECT COUNT(*) FROM payments WHERE reserve_number = c.reserve_number) as p_count
    FROM charters c
    WHERE c.paid_amount > 0
      AND NOT EXISTS (
          SELECT 1 FROM charter_payments WHERE charter_id = c.reserve_number
      )
      AND NOT EXISTS (
          SELECT 1 FROM payments WHERE reserve_number = c.reserve_number
      )
    ORDER BY c.paid_amount DESC, c.charter_date DESC
""")
rows = cur.fetchall()

if not rows:
    print('\nNo charters with orphaned paid_amount found.')
    cur.close()
    conn.close()
    exit(0)

print(f'\nTotal charters with orphaned paid_amount: {len(rows)}')

total_orphaned = sum(r[6] for r in rows)
print(f'Total orphaned paid_amount: ${total_orphaned:,.2f}')

print('\nTop 50 by paid_amount (descending):')
for r in rows[:50]:
    reserve_number, charter_date, account_number, status, cancelled, total_amount_due, paid_amount, balance, cp_count, p_count = r
    print(f'  {reserve_number} date={charter_date} acct={account_number} status={status} cancelled={cancelled}')
    print(f'    total_due={total_amount_due} paid=${paid_amount} balance={balance}')

# Export CSV
os.makedirs('reports', exist_ok=True)
outfile = 'reports/charters_orphaned_payments.csv'
with open(outfile, 'w', newline='', encoding='utf-8') as f:
    w = csv.writer(f)
    w.writerow(['Reserve Number', 'Charter Date', 'Account Number', 'Status', 'Cancelled',
                'Total Amount Due', 'Paid Amount', 'Balance', 'CP Count', 'P Count'])
    for r in rows:
        w.writerow(r)

print(f'\nCSV exported: {outfile}')

cur.close()
conn.close()
print('\nDone.')
