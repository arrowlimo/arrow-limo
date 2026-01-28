#!/usr/bin/env python3
"""
Identify missing months of banking data for account 3648117 (CIBC Business Deposit).
"""
import psycopg2
from datetime import datetime
from collections import defaultdict

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

# Get all transactions for account 3648117
cur.execute("""
    SELECT 
        EXTRACT(YEAR FROM transaction_date) as year,
        EXTRACT(MONTH FROM transaction_date) as month,
        COUNT(*) as count
    FROM banking_transactions
    WHERE account_number = '3648117'
    GROUP BY year, month
    ORDER BY year, month
""")

months_with_data = {}
for year, month, count in cur.fetchall():
    year_int = int(year)
    month_int = int(month)
    if year_int not in months_with_data:
        months_with_data[year_int] = {}
    months_with_data[year_int][month_int] = count

# Also get the date range
cur.execute("""
    SELECT 
        MIN(transaction_date) as earliest,
        MAX(transaction_date) as latest
    FROM banking_transactions
    WHERE account_number = '3648117'
""")

earliest, latest = cur.fetchone()

cur.close()
conn.close()

print("=" * 80)
print("ACCOUNT 3648117 (CIBC Business Deposit) - TRANSACTION COVERAGE")
print("=" * 80)
print()

if earliest and latest:
    print(f"Date Range: {earliest} to {latest}")
    print()
    
    # Generate all months in the range
    start_year = earliest.year
    start_month = earliest.month
    end_year = latest.year
    end_month = latest.month
    
    print("MONTH-BY-MONTH BREAKDOWN:")
    print(f"{'Year':<6} {'Month':<12} {'Txns':>6} {'Status':<20}")
    print("-" * 50)
    
    missing_months = []
    current_year = start_year
    current_month = start_month
    
    month_names = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    
    while (current_year < end_year) or (current_year == end_year and current_month <= end_month):
        month_name = month_names[current_month]
        
        if current_year in months_with_data and current_month in months_with_data[current_year]:
            count = months_with_data[current_year][current_month]
            status = "✓ Has data"
            print(f"{current_year:<6} {month_name:<12} {count:>6} {status:<20}")
        else:
            status = "✗ MISSING"
            print(f"{current_year:<6} {month_name:<12} {'0':>6} {status:<20}")
            missing_months.append(f"{current_year}-{current_month:02d} ({month_name})")
        
        # Move to next month
        current_month += 1
        if current_month > 12:
            current_month = 1
            current_year += 1
    
    print()
    print("=" * 80)
    print(f"SUMMARY: {len(missing_months)} MISSING MONTHS")
    print("=" * 80)
    
    if missing_months:
        print()
        for m in missing_months:
            print(f"  • {m}")
    else:
        print("\n✓ All months have data")
    
else:
    print("No transactions found for account 3648117")
