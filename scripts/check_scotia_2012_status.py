#!/usr/bin/env python3
"""Check Scotia Bank 2012 import status."""
import psycopg2
import os

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REMOVED***'
)
cur = conn.cursor()

cur.execute("""
    SELECT 
        TO_CHAR(transaction_date, 'YYYY-MM') as month,
        COUNT(*) as count,
        SUM(debit_amount) as debits,
        SUM(credit_amount) as credits
    FROM banking_transactions
    WHERE account_number = '3714081'
    AND transaction_date >= '2012-01-01'
    AND transaction_date < '2013-01-01'
    GROUP BY month
    ORDER BY month
""")

print("\nScotia Bank 2012 Monthly Breakdown:")
print("=" * 80)
total_rows = 0
total_debits = 0
total_credits = 0

for row in cur.fetchall():
    month, count, debits, credits = row
    total_rows += count
    total_debits += debits or 0
    total_credits += credits or 0
    print(f"{month}: {count:4d} rows | Debits: ${debits or 0:>12,.2f} | Credits: ${credits or 0:>12,.2f}")

print("=" * 80)
print(f"TOTAL: {total_rows:4d} rows | Debits: ${total_debits:>12,.2f} | Credits: ${total_credits:>12,.2f}")

# Check for missing files
print("\n\nMissing CSV Files to Import:")
print("=" * 80)

import glob
missing_files = sorted(glob.glob(r'l:\limo\reports\missing_banking_rows_scotia_*2012*.csv'))
print(f"Found {len(missing_files)} CSV files in l:\\limo\\reports\\")

# Group by month
from collections import defaultdict
by_month = defaultdict(list)
for f in missing_files:
    fname = os.path.basename(f)
    if 'jan2012' in fname:
        by_month['Jan'].append(fname)
    elif 'feb2012' in fname:
        by_month['Feb'].append(fname)
    elif 'mar2012' in fname:
        by_month['Mar'].append(fname)
    elif 'apr2012' in fname:
        by_month['Apr'].append(fname)
    elif 'may2012' in fname:
        by_month['May'].append(fname)
    elif 'jun2012' in fname:
        by_month['Jun'].append(fname)
    elif 'jul2012' in fname:
        by_month['Jul'].append(fname)
    elif 'aug2012' in fname:
        by_month['Aug'].append(fname)
    elif 'sep2012' in fname:
        by_month['Sep'].append(fname)
    elif 'oct2012' in fname:
        by_month['Oct'].append(fname)
    elif 'nov2012' in fname:
        by_month['Nov'].append(fname)
    elif 'dec2012' in fname:
        by_month['Dec'].append(fname)

for month in ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']:
    files = by_month.get(month, [])
    if files:
        print(f"\n{month} 2012: {len(files)} files")
        for f in files[:3]:
            print(f"  - {f}")
        if len(files) > 3:
            print(f"  ... and {len(files)-3} more")

cur.close()
conn.close()
