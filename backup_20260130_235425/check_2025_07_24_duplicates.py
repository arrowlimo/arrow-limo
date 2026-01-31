#!/usr/bin/env python
"""
Check for duplicate payments from 2025-07-24 batch import.
Identify charters where payments appear to be duplicated from that date.
"""
import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()

print('='*100)
print('CHECK FOR DUPLICATE 2025-07-24 BATCH PAYMENTS')
print('='*100)

# Find all payments from 2025-07-24
cur.execute("""
    SELECT payment_id, reserve_number, amount, payment_method
    FROM payments
    WHERE payment_date = '2025-07-24'
    ORDER BY reserve_number, amount
""")
payments_2025_07_24 = cur.fetchall()

print(f'\nTotal payments from 2025-07-24: {len(payments_2025_07_24)}')

# Group by reserve_number to find potential duplicates
from collections import defaultdict
by_reserve = defaultdict(list)
for p in payments_2025_07_24:
    if p[1]:  # Skip NULL reserve_numbers
        by_reserve[p[1]].append(p)

print(f'Affecting {len(by_reserve)} unique reserve numbers')

# Check for duplicates: same reserve + same amount = potential duplicate
print('\n' + '='*100)
print('CHECKING FOR DUPLICATE PATTERNS')
print('='*100)

duplicates_found = []

for reserve, payments in sorted(by_reserve.items()):
    if len(payments) > 1:
        print(f'\n{reserve}: {len(payments)} payments on 2025-07-24')
        for p in payments:
            print(f'  payment_id={p[0]}: ${p[2]} via {p[3]}')
        
        # Check if any amounts match (potential duplicate)
        amounts = [p[2] for p in payments]
        if len(amounts) != len(set(amounts)):
            print(f'  [WARN]  DUPLICATE AMOUNTS DETECTED')
            duplicates_found.append(reserve)

# For each reserve with 2025-07-24 payments, check if there are older payments with same amounts
print('\n' + '='*100)
print('CHECKING FOR DUPLICATES OF EARLIER PAYMENTS')
print('='*100)

potential_dupes = []

for reserve, jul24_payments in sorted(by_reserve.items()):
    # Get all OTHER payments for this reserve (not from 2025-07-24)
    cur.execute("""
        SELECT payment_id, amount, payment_date, payment_method
        FROM payments
        WHERE reserve_number = %s
          AND payment_date != '2025-07-24'
        ORDER BY payment_date
    """, (reserve,))
    other_payments = cur.fetchall()
    
    if not other_payments:
        continue
    
    # Check if any 2025-07-24 payment matches an earlier payment amount
    jul24_amounts = {p[2] for p in jul24_payments}
    other_amounts = {p[1] for p in other_payments}
    
    matching_amounts = jul24_amounts & other_amounts
    
    if matching_amounts:
        print(f'\n{reserve}: Possible duplicates found')
        print(f'  Earlier payments:')
        for p in other_payments:
            marker = ' ← DUPLICATE' if p[1] in matching_amounts else ''
            print(f'    payment_id={p[0]}: ${p[1]} on {p[2]}{marker}')
        print(f'  2025-07-24 payments:')
        for p in jul24_payments:
            marker = ' ← DUPLICATE' if p[2] in matching_amounts else ''
            print(f'    payment_id={p[0]}: ${p[2]}{marker}')
        potential_dupes.append(reserve)

print('\n' + '='*100)
print('SUMMARY')
print('='*100)
print(f'\nTotal 2025-07-24 payments: {len(payments_2025_07_24)}')
print(f'Reserves affected: {len(by_reserve)}')
print(f'Reserves with multiple 2025-07-24 payments: {sum(1 for p in by_reserve.values() if len(p) > 1)}')
print(f'Reserves with matching amounts on same day: {len(duplicates_found)}')
print(f'Reserves with potential duplicates of earlier payments: {len(potential_dupes)}')

if potential_dupes:
    print(f'\n[WARN]  {len(potential_dupes)} reserves may have duplicate payments from 2025-07-24 batch:')
    for r in potential_dupes:
        print(f'  {r}')
else:
    print('\n[OK] No duplicate patterns detected from 2025-07-24 batch')

cur.close()
conn.close()
print('\nDone.')
