#!/usr/bin/env python
"""
List outstanding balances (after removing 2025-07-24 duplicates) excluding Nov 2025 onward.
Shows what payments are actually missing from historical charters.
"""
import psycopg2
import csv

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

print('='*100)
print('OUTSTANDING BALANCES (EXCLUDING NOV 2025 ONWARD)')
print('='*100)

# Calculate what balance would be after removing 2025-07-24 duplicates
cur.execute("""
    WITH duplicate_amounts AS (
        SELECT 
            p_dup.reserve_number,
            SUM(p_dup.amount) as duplicate_amount
        FROM payments p_dup
        WHERE p_dup.payment_date = '2025-07-24'
          AND p_dup.reserve_number IS NOT NULL
          AND EXISTS (
              SELECT 1 FROM payments p_earlier
              WHERE p_earlier.reserve_number = p_dup.reserve_number
                AND p_earlier.amount = p_dup.amount
                AND p_earlier.payment_date < '2025-07-24'
          )
        GROUP BY p_dup.reserve_number
    )
    SELECT 
        c.reserve_number,
        c.charter_date,
        cl.client_name,
        c.total_amount_due,
        c.paid_amount,
        c.balance as current_balance,
        COALESCE(d.duplicate_amount, 0) as duplicate_removal,
        c.balance + COALESCE(d.duplicate_amount, 0) as corrected_balance,
        c.status,
        c.cancelled
    FROM charters c
    LEFT JOIN clients cl ON cl.client_id = c.client_id
    LEFT JOIN duplicate_amounts d ON d.reserve_number = c.reserve_number
    WHERE c.charter_date < '2025-11-01'
      AND c.total_amount_due > 0
      AND (c.balance + COALESCE(d.duplicate_amount, 0)) > 0.50
      AND COALESCE(c.cancelled, FALSE) = FALSE
      AND COALESCE(c.status, '') NOT ILIKE '%cancel%'
    ORDER BY (c.balance + COALESCE(d.duplicate_amount, 0)) DESC
""")
outstanding = cur.fetchall()

print(f'\nFound {len(outstanding)} charters with outstanding balances')
total_outstanding = sum(r[7] for r in outstanding)
print(f'Total outstanding: ${total_outstanding:,.2f}')

# Summary by year
from collections import defaultdict
by_year = defaultdict(lambda: {'count': 0, 'amount': 0})
for r in outstanding:
    if r[1]:  # charter_date
        year = r[1].year
        by_year[year]['count'] += 1
        by_year[year]['amount'] += r[7]

print('\nOutstanding by Year:')
for year in sorted(by_year.keys()):
    print(f'  {year}: {by_year[year]["count"]:,} charters, ${by_year[year]["amount"]:,.2f}')

# Top 50 largest outstanding
print('\n' + '='*100)
print('TOP 50 LARGEST OUTSTANDING BALANCES')
print('='*100)
print(f'\n{"Reserve":<10} {"Date":<12} {"Client":<30} {"Total Due":<12} {"Paid":<12} {"Corrected":<12} {"Status":<15}')
print('-'*100)

for r in outstanding[:50]:
    reserve = r[0] or ''
    date = r[1].strftime('%Y-%m-%d') if r[1] else ''
    client = (r[2] or '')[:28]
    total_due = f'${r[3] or 0:,.2f}'
    paid = f'${r[4] or 0:,.2f}'
    corrected = f'${r[7]:,.2f}'
    status = (r[8] or '')[:13]
    
    print(f'{reserve:<10} {date:<12} {client:<30} {total_due:<12} {paid:<12} {corrected:<12} {status:<15}')

# Export to CSV
csv_file = 'outstanding_balances_pre_nov2025.csv'
with open(csv_file, 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerow(['Reserve', 'Date', 'Client', 'Total_Due', 'Paid', 'Current_Balance', 
                     'Duplicate_Removal', 'Corrected_Balance', 'Status', 'Cancelled'])
    for r in outstanding:
        writer.writerow([
            r[0],
            r[1].strftime('%Y-%m-%d') if r[1] else '',
            r[2],
            r[3],
            r[4],
            r[5],
            r[6],
            r[7],
            r[8],
            r[9]
        ])

print(f'\n✓ Full report exported to: {csv_file}')

# Categories of outstanding
print('\n' + '='*100)
print('OUTSTANDING CATEGORIES')
print('='*100)

cur.execute("""
    WITH duplicate_amounts AS (
        SELECT 
            p_dup.reserve_number,
            SUM(p_dup.amount) as duplicate_amount
        FROM payments p_dup
        WHERE p_dup.payment_date = '2025-07-24'
          AND p_dup.reserve_number IS NOT NULL
          AND EXISTS (
              SELECT 1 FROM payments p_earlier
              WHERE p_earlier.reserve_number = p_dup.reserve_number
                AND p_earlier.amount = p_dup.amount
                AND p_earlier.payment_date < '2025-07-24'
          )
        GROUP BY p_dup.reserve_number
    ),
    corrected_balances AS (
        SELECT 
            c.reserve_number,
            c.balance + COALESCE(d.duplicate_amount, 0) as corrected_balance
        FROM charters c
        LEFT JOIN duplicate_amounts d ON d.reserve_number = c.reserve_number
        WHERE c.charter_date < '2025-11-01'
          AND c.total_amount_due > 0
          AND COALESCE(c.cancelled, FALSE) = FALSE
          AND COALESCE(c.status, '') NOT ILIKE '%cancel%'
    )
    SELECT 
        CASE 
            WHEN corrected_balance > 2000 THEN 'Large (>$2K)'
            WHEN corrected_balance > 500 THEN 'Medium ($500-$2K)'
            WHEN corrected_balance > 100 THEN 'Small ($100-$500)'
            WHEN corrected_balance > 0.50 THEN 'Minimal (<$100)'
            ELSE 'Paid/Credit'
        END as category,
        COUNT(*) as count,
        SUM(corrected_balance) as total
    FROM corrected_balances
    GROUP BY category
    ORDER BY total DESC
""")
categories = cur.fetchall()

for cat in categories:
    print(f'  {cat[0]:<20} {cat[1]:>6} charters, ${cat[2]:>12,.2f}')

cur.close()
conn.close()
print('\nDone.')
