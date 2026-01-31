#!/usr/bin/env python3
import csv

rows = list(csv.DictReader(open('l:/limo/reports/square_lms_matches_postgres_20260107_233316.csv', encoding='utf-8')))
print(f'Total unmatched: {len(rows)}')
matched = [r for r in rows if r['reserve_number']]
print(f'With reserve match: {len(matched)}')
print(f'No reserve found: {len(rows) - len(matched)}')

if matched:
    methods = {}
    for r in matched:
        m = r['match_method']
        methods[m] = methods.get(m, 0) + 1
    print('\nMatch methods:')
    for k, v in sorted(methods.items(), key=lambda x: -x[1]):
        print(f'  {k}: {v}')
    
    print(f'\nSample matched (first 5):')
    for r in matched[:5]:
        print(f"  {r['payment_id']}: ${float(r['payment_amount']):.2f} → {r['reserve_number']} ({r['match_method']})")
