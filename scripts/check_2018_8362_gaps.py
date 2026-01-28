#!/usr/bin/env python
"""Check for missing dates in 2018 for CIBC 8362 account."""
import psycopg2
import os
from datetime import date, timedelta

DB_HOST=os.environ.get("DB_HOST","localhost")
DB_NAME=os.environ.get("DB_NAME","almsdata")
DB_USER=os.environ.get("DB_USER","postgres")
DB_PASSWORD=os.environ.get("DB_PASSWORD",os.environ.get("DB_PASSWORD"))

conn=psycopg2.connect(host=DB_HOST,database=DB_NAME,user=DB_USER,password=DB_PASSWORD)
cur=conn.cursor()

print("\n"+"="*80)
print("2018 DATE COVERAGE FOR CIBC 8362")
print("="*80)

# Get all distinct dates in 2018 for 8362
cur.execute("""
    SELECT DISTINCT transaction_date::date
    FROM banking_transactions
    WHERE EXTRACT(YEAR FROM transaction_date)=2018
      AND source_file LIKE '%8362%'
    ORDER BY transaction_date
""")
rows=cur.fetchall()

if not rows:
    print("❌ No 2018 transactions found for 8362")
    cur.close(); conn.close()
    exit(0)

existing_dates = set(row[0] for row in rows)
print(f"Found {len(existing_dates)} distinct dates with transactions\n")

# Generate all dates in 2018
start_date = date(2018, 1, 1)
end_date = date(2018, 12, 31)
all_dates = []
current = start_date
while current <= end_date:
    all_dates.append(current)
    current += timedelta(days=1)

# Find missing dates
missing = [d for d in all_dates if d not in existing_dates]

print(f"Total days in 2018: {len(all_dates)}")
print(f"Days with transactions: {len(existing_dates)}")
print(f"Missing days: {len(missing)}\n")

if missing:
    print("Missing date ranges:")
    print("-" * 80)
    
    # Group consecutive missing dates into ranges
    ranges = []
    start_missing = missing[0]
    prev = missing[0]
    
    for d in missing[1:]:
        if (d - prev).days > 1:
            # Gap - close current range
            ranges.append((start_missing, prev))
            start_missing = d
        prev = d
    ranges.append((start_missing, prev))
    
    for start, end in ranges:
        if start == end:
            print(f"  {start.strftime('%Y-%m-%d')} (1 day)")
        else:
            days = (end - start).days + 1
            print(f"  {start.strftime('%Y-%m-%d')} to {end.strftime('%Y-%m-%d')} ({days} days)")
else:
    print("✅ No missing dates - complete coverage for 2018")

# Get first and last transaction dates
print(f"\nFirst transaction: {min(existing_dates)}")
print(f"Last transaction:  {max(existing_dates)}")

# Check source file distribution
cur.execute("""
    SELECT source_file, COUNT(*), MIN(transaction_date::date), MAX(transaction_date::date)
    FROM banking_transactions
    WHERE EXTRACT(YEAR FROM transaction_date)=2018
      AND source_file LIKE '%8362%'
    GROUP BY source_file
    ORDER BY MIN(transaction_date)
""")
print("\nSource file breakdown:")
for row in cur.fetchall():
    print(f"  {row[0]}: {row[1]} transactions ({row[2]} to {row[3]})")

cur.close(); conn.close()
