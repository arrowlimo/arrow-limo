#!/usr/bin/env python3
"""
Analyze cheque payee names from CIBC QuickBooks reconciliation.
"""

import csv
from collections import defaultdict

CSV_PATH = r"l:\limo\data\cibc_qb_reconciliation_consolidated.csv"

print("\n" + "="*80)
print("CIBC CHEQUE PAYEE NAMES ANALYSIS")
print("="*80)

# Load CSV
with open(CSV_PATH, 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    rows = list(reader)

# Filter cheques only
cheques = [r for r in rows if 'cheque' in r['type'].lower()]
print(f"\nTotal cheques: {len(cheques)}")

# Group by payee name
by_name = defaultdict(lambda: {'count': 0, 'total': 0.0})
for cheque in cheques:
    name = cheque['name'].strip()
    if name and name != '-':
        by_name[name]['count'] += 1
        by_name[name]['total'] += abs(float(cheque['amount']))

print(f"Unique payee names: {len(by_name)}")

# Sort by count (most frequent first)
sorted_names = sorted(by_name.items(), key=lambda x: x[1]['count'], reverse=True)

print("\n" + "="*80)
print("TOP 50 PAYEES (by transaction count)")
print("="*80)
print(f"{'Payee Name':50} {'Count':>6} {'Total':>15}")
print("-"*80)

for i, (name, stats) in enumerate(sorted_names[:50], 1):
    print(f"{name[:50]:50} {stats['count']:6} ${stats['total']:>13,.2f}")

if len(sorted_names) > 50:
    remaining = len(sorted_names) - 50
    remaining_total = sum(stats['total'] for name, stats in sorted_names[50:])
    print(f"\n... and {remaining} more payees (${remaining_total:,.2f})")

# Show some interesting categories
print("\n" + "="*80)
print("INTERESTING PATTERNS")
print("="*80)

# Fuel vendors
fuel_vendors = [n for n in by_name.keys() if any(x in n.lower() for x in ['centex', 'shell', 'esso', 'petro', 'fas gas', 'husky'])]
if fuel_vendors:
    print(f"\nFuel vendors ({len(fuel_vendors)}):")
    for vendor in sorted(fuel_vendors)[:20]:
        stats = by_name[vendor]
        print(f"  {vendor[:50]:50} {stats['count']:3} txns ${stats['total']:>12,.2f}")

# Names with 'X' marker (cleared)
cleared = [n for n in by_name.keys() if n.endswith('X')]
print(f"\nCleared transactions (ending with 'X'): {len(cleared)}")
print(f"  Example: {cleared[0] if cleared else 'None'}")

# Driver/employee names
potential_drivers = [n for n in by_name.keys() if any(x in n.lower() for x in ['paul', 'jesse', 'jack', 'angel', 'chantal', 'dustan'])]
if potential_drivers:
    print(f"\nPotential driver payments ({len(potential_drivers)}):")
    for name in sorted(potential_drivers):
        stats = by_name[name]
        print(f"  {name[:50]:50} {stats['count']:3} txns ${stats['total']:>12,.2f}")

print("\n" + "="*80)
