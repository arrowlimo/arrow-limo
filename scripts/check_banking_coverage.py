#!/usr/bin/env python3
import psycopg2
from collections import defaultdict

conn = psycopg2.connect(dbname='almsdata', user='postgres', password='***REMOVED***', host='localhost')
cur = conn.cursor()

print('='*80)
print('BANKING TRANSACTION COVERAGE BY YEAR')
print('='*80)

cur.execute("""
    SELECT 
        EXTRACT(YEAR FROM transaction_date) as year,
        COUNT(*) as transaction_count,
        MIN(transaction_date) as first_date,
        MAX(transaction_date) as last_date,
        COUNT(DISTINCT EXTRACT(MONTH FROM transaction_date)) as months_with_data
    FROM banking_transactions
    WHERE transaction_date IS NOT NULL
    GROUP BY EXTRACT(YEAR FROM transaction_date)
    ORDER BY year
""")

rows = cur.fetchall()

print(f"\n{'Year':<6} {'Transactions':<15} {'First Date':<12} {'Last Date':<12} {'Months':<8}")
print('-'*80)

for year, count, first_dt, last_dt, months in rows:
    year_int = int(year)
    status = 'FULL' if months == 12 else f'PARTIAL ({months}/12)'
    print(f"{year_int:<6} {count:<15,} {str(first_dt):<12} {str(last_dt):<12} {status}")

# Check for gaps in coverage
print('\n' + '='*80)
print('DETAILED MONTHLY COVERAGE')
print('='*80)

cur.execute("""
    SELECT 
        EXTRACT(YEAR FROM transaction_date) as year,
        EXTRACT(MONTH FROM transaction_date) as month,
        COUNT(*) as count
    FROM banking_transactions
    WHERE transaction_date IS NOT NULL
    GROUP BY EXTRACT(YEAR FROM transaction_date), EXTRACT(MONTH FROM transaction_date)
    ORDER BY year, month
""")

by_year_month = defaultdict(dict)
for year, month, count in cur.fetchall():
    by_year_month[int(year)][int(month)] = count

# Show years with missing months
print("\nYears with missing months:")
for year in sorted(by_year_month.keys()):
    months = by_year_month[year]
    missing = [m for m in range(1,13) if m not in months]
    if missing:
        missing_str = ', '.join(f'{m:02d}' for m in missing)
        print(f"  {year}: Missing months {missing_str}")

# Check for years with no data at all
cur.execute("SELECT MIN(EXTRACT(YEAR FROM transaction_date)), MAX(EXTRACT(YEAR FROM transaction_date)) FROM banking_transactions")
min_year, max_year = cur.fetchone()
min_year, max_year = int(min_year), int(max_year)

years_with_no_data = []
for y in range(2007, 2026):  # Check business operation range
    if y not in by_year_month:
        years_with_no_data.append(y)

if years_with_no_data:
    print(f"\nYears with NO banking data: {', '.join(map(str, years_with_no_data))}")

print('\n' + '='*80)
print('SUMMARY')
print('='*80)
print(f"Banking data range: {min_year} - {max_year}")
print(f"Total years covered: {len(by_year_month)}")
print(f"Years with full 12 months: {sum(1 for y in by_year_month if len(by_year_month[y]) == 12)}")
print(f"Years with partial data: {sum(1 for y in by_year_month if len(by_year_month[y]) < 12)}")

cur.close()
conn.close()
