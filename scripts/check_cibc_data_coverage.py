#!/usr/bin/env python3
"""Check which years have CIBC banking data and identify gaps."""

import psycopg2
from datetime import datetime

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REDACTED***'
)
cur = conn.cursor()

print("="*100)
print("CIBC ACCOUNT 0228362 - BANKING DATA COVERAGE")
print("="*100)

cur.execute("""
    SELECT 
        EXTRACT(YEAR FROM transaction_date) as year, 
        COUNT(*) as count, 
        MIN(transaction_date) as first_date, 
        MAX(transaction_date) as last_date,
        SUM(debit_amount) as total_debits,
        SUM(credit_amount) as total_credits
    FROM banking_transactions 
    WHERE account_number = '0228362'
    GROUP BY year 
    ORDER BY year
""")

rows = cur.fetchall()

print(f"\n{'Year':<6} {'Count':<8} {'First Date':<12} {'Last Date':<12} {'Total Debits':<18} {'Total Credits':<18}")
print("-"*100)

years_with_data = []
for row in rows:
    year = int(row[0])
    count = row[1]
    first = str(row[2])
    last = str(row[3])
    debits = float(row[4] or 0)
    credits = float(row[5] or 0)
    years_with_data.append(year)
    print(f"{year:<6} {count:<8} {first:<12} {last:<12} ${debits:>15,.2f} ${credits:>15,.2f}")

print("-"*100)

if years_with_data:
    min_year = min(years_with_data)
    max_year = max(years_with_data)
    all_years = list(range(min_year, max_year + 1))
    missing_years = [y for y in all_years if y not in years_with_data]
    
    print(f"\nData Range: {min_year} - {max_year}")
    print(f"Years with data: {len(years_with_data)}")
    print(f"Missing years: {missing_years if missing_years else 'None - complete coverage!'}")
    
    # Check current year
    current_year = datetime.now().year
    if max_year < current_year:
        print(f"\nNote: No data yet for {current_year} (current year)")
    
    # Suggest next years to import
    if missing_years:
        print(f"\n⚠ GAPS DETECTED: Need to import data for years: {', '.join(map(str, missing_years))}")
    else:
        print(f"\n✓ Complete coverage from {min_year} to {max_year}")
else:
    print("\nNo CIBC banking data found in database!")

conn.close()
