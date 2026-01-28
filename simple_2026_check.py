#!/usr/bin/env python3
"""Simple check: Are remaining charters from 2026?"""
import psycopg2
import os

DB_HOST = os.environ.get('DB_HOST', 'localhost')
DB_NAME = os.environ.get('DB_NAME', 'almsdata')
DB_USER = os.environ.get('DB_USER', 'postgres')
DB_PASSWORD = os.environ.get('DB_PASSWORD', os.environ.get("DB_PASSWORD"))

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

cur.execute('''
    SELECT 
        charter_id,
        reserve_number,
        charter_date,
        status,
        total_amount_due,
        paid_amount
    FROM charters
    WHERE total_amount_due > 0
      AND ABS(total_amount_due - paid_amount) >= 0.10
    ORDER BY charter_date DESC NULLS LAST;
''')

results = cur.fetchall()
cur.close()
conn.close()

# Count by year
year_counts = {}
for row in results:
    charter_date = row[2]
    if charter_date:
        year = charter_date.year
        year_counts[year] = year_counts.get(year, 0) + 1
    else:
        year_counts[None] = year_counts.get(None, 0) + 1

print(f"\n{'='*80}")
print(f"REMAINING {len(results)} CHARTERS - BY YEAR")
print(f"{'='*80}\n")

for year in sorted([y for y in year_counts.keys() if y], reverse=True):
    print(f"  {year}: {year_counts[year]} charters")

if None in year_counts:
    print(f"  No Date: {year_counts[None]} charters")

# Show 2026 details
charters_2026 = [r for r in results if r[2] and r[2].year == 2026]
if charters_2026:
    print(f"\n{'='*80}")
    print(f"✅ YES - {len(charters_2026)} charters are from 2026:")
    print(f"{'='*80}")
    print(f"Charter  | Reserve  | Pickup Date | Status          | Due        | Paid")
    print(f"{'-'*80}")
    for r in charters_2026[:20]:  # Show first 20
        print(f"{r[0]:<8} | {r[1] or 'N/A':<8} | {r[2]} | {(r[3] or 'Unknown')[:14]:<14} | ${r[4]:>10.2f} | ${r[5]:>10.2f}")
    if len(charters_2026) > 20:
        print(f"... and {len(charters_2026) - 20} more")
else:
    print(f"\n❌ NO - None of the {len(results)} charters are from 2026")

print(f"\n{'='*80}\n")
