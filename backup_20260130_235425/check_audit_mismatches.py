import csv

rows = list(csv.DictReader(open('reports/audit_charge_mismatches.csv', encoding='utf-8')))
print(f'Total charge mismatches: {len(rows)}\n')

print('Columns:', list(rows[0].keys()) if rows else 'None')

print('\nFirst 10:')
for i, r in enumerate(rows[:10], 1):
    print(f"{i}. {r}")
