#!/usr/bin/env python3
"""List unmatched banking deposits grouped by amount ranges."""
import psycopg2
import os
from datetime import datetime
from collections import defaultdict

DB_HOST = os.environ.get('DB_HOST', 'localhost')
DB_NAME = os.environ.get('DB_NAME', 'almsdata')
DB_USER = os.environ.get('DB_USER', 'postgres')
DB_PASSWORD = os.environ.get('DB_PASSWORD', '***REMOVED***')

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

# Phase 1: Find unmatched banking deposits
query = '''
SELECT 
    bt.transaction_id,
    bt.transaction_date,
    bt.credit_amount,
    bt.description,
    bt.account_number
FROM banking_transactions bt
WHERE bt.credit_amount > 0
  AND NOT EXISTS (
    SELECT 1 FROM payments p 
    WHERE ABS(p.amount - bt.credit_amount) < 0.01
      AND p.payment_date::date >= bt.transaction_date::date - INTERVAL '7 days'
      AND p.payment_date::date <= bt.transaction_date::date + INTERVAL '7 days'
  )
ORDER BY bt.transaction_date DESC, bt.credit_amount DESC;
'''

cur.execute(query)
results = cur.fetchall()
cur.close()
conn.close()

# Group by amount ranges
groups = defaultdict(list)
for row in results:
    amount = row[2]
    if amount < 100:
        group = '$0-$100'
    elif amount < 500:
        group = '$100-$500'
    elif amount < 1000:
        group = '$500-$1K'
    elif amount < 5000:
        group = '$1K-$5K'
    elif amount < 10000:
        group = '$5K-$10K'
    else:
        group = '$10K+'
    groups[group].append(row)

# Display groups
print("\n" + "=" * 120)
print("UNMATCHED BANKING DEPOSITS - GROUPED BY AMOUNT".center(120))
print("=" * 120)

total_amount = 0
total_count = 0

for group in ['$0-$100', '$100-$500', '$500-$1K', '$1K-$5K', '$5K-$10K', '$10K+']:
    if group not in groups:
        continue
    
    items = groups[group]
    group_sum = sum(item[2] for item in items)
    total_amount += group_sum
    total_count += len(items)
    
    print(f"\n{group} ({len(items)} deposits, Total: ${group_sum:,.2f})")
    print("-" * 120)
    print(f"{'ID':<8} | {'Date':<12} | {'Amount':>12} | {'Account':<10} | {'Description':<50}")
    print("-" * 120)
    
    for item in items[:20]:  # Show first 20 in each group
        tid, date, amount, desc, account = item
        desc_short = (desc[:45] + '...') if desc and len(desc) > 50 else (desc or '')
        acct_short = (account[-4:] if account else 'N/A')
        print(f"{tid:<8} | {str(date)[:10]:<12} | {amount:>12.2f} | {acct_short:<10} | {desc_short:<50}")
    
    if len(items) > 20:
        print(f"... and {len(items) - 20} more items in this group")

print("\n" + "=" * 120)
print(f"SUMMARY: {total_count} unmatched deposits | Total: ${total_amount:,.2f}")
print("=" * 120)
