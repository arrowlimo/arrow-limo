#!/usr/bin/env python3
"""Check if remaining 85 charters are from 2026."""
import psycopg2
import os
from datetime import datetime

DB_HOST = os.environ.get('DB_HOST', 'localhost')
DB_NAME = os.environ.get('DB_NAME', 'almsdata')
DB_USER = os.environ.get('DB_USER', 'postgres')
DB_PASSWORD = os.environ.get('DB_PASSWORD', os.environ.get("DB_PASSWORD"))

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

# Get remaining unbalanced with dates
cur.execute('''
    SELECT 
        c.charter_id,
        c.reserve_number,
        c.total_amount_due,
        c.paid_amount,
        (c.total_amount_due - c.paid_amount) as balance,
        c.status,
        c.pickup_time::text
    FROM charters c
    WHERE c.total_amount_due > 0
      AND ABS(c.total_amount_due - c.paid_amount) >= 0.10
    ORDER BY c.pickup_time DESC NULLS LAST;
''')

results = cur.fetchall()
cur.close()
conn.close()

print("\n" + "=" * 100)
print("REMAINING 85 CHARTERS - YEAR ANALYSIS".center(100))
print("=" * 100)
print(f"\nTotal Remaining: {len(results)} charters\n")

# Group by year
by_year = {}
for row in results:
    pickup_str = row[6]
    # Parse year from pickup_time string (format: HH:MM:SS or date-like)
    # Since pickup_time might be just time, check pickup_date instead
    year = None
    if pickup_str and len(pickup_str) >= 4:
        try:
            # If it looks like a date string, extract year
            if '-' in pickup_str or '/' in pickup_str:
                year_str = pickup_str[:4]
                if year_str.isdigit():
                    year = int(year_str)
        except:
            pass
    
    if year not in by_year:
        by_year[year] = []
    by_year[year].append(row)

print("📊 BY YEAR:")
print("-" * 100)
for year in sorted([y for y in by_year.keys() if y is not None], reverse=True):
    count = len(by_year[year])
    total_balance = sum(abs(r[4]) for r in by_year[year])
    print(f"   {year}:  {count:>3} charters | ${total_balance:>12,.2f} balance")

if None in by_year:
    count = len(by_year[None])
    total_balance = sum(abs(r[4]) for r in by_year[None])
    print(f"   No Date: {count:>3} charters | ${total_balance:>12,.2f} balance")

# Show 2026 charters if any
if 2026 in by_year:
    charters_2026 = by_year[2026]
    print(f"\n" + "=" * 100)
    print(f"🔍 2026 CHARTERS ({len(charters_2026)} total):")
    print("=" * 100)
    print("Charter  | Reserve  | Due        | Paid       | Balance    | Pickup Date | Status")
    print("-" * 100)
    
    for row in charters_2026:
        charter_id, reserve, due, paid, balance, status, pickup = row
        reserve_str = reserve or 'N/A'
        pickup_str = pickup if pickup else 'N/A'
        status_str = (status[:12] if status else 'Unknown').ljust(12)
        print(f"{charter_id:<8} | {reserve_str:<8} | ${due:>10.2f} | ${paid:>10.2f} | ${balance:>10.2f} | {pickup_str} | {status_str}")
    
    print(f"\n✅ YES - {len(charters_2026)} of {len(results)} remaining charters are from 2026")
    print(f"   Total 2026 balance: ${sum(abs(r[4]) for r in charters_2026):,.2f}")
else:
    print(f"\n❌ NO - None of the remaining {len(results)} charters are from 2026")

# Show most recent year
if by_year:
    most_recent_year = max([y for y in by_year.keys() if y is not None])
    print(f"\n📅 Most recent year: {most_recent_year}")
    print(f"   Current date: {datetime.now().strftime('%Y-%m-%d')}")

print("\n" + "=" * 100 + "\n")
