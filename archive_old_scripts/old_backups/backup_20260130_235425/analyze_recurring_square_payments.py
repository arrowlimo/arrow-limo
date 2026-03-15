#!/usr/bin/env python3
"""Detailed analysis of recurring Square payments."""
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from collections import defaultdict

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_NAME = os.getenv("DB_NAME", "almsdata")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")

conn = psycopg2.connect(host=DB_HOST, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor(cursor_factory=RealDictCursor)

# Get unmatched Square payments
cur.execute("""
    SELECT payment_id, amount, payment_date, payment_key
    FROM payments
    WHERE payment_method = 'credit_card'
      AND payment_key IS NOT NULL
      AND charter_id IS NULL
    ORDER BY payment_date
""")
unmatched = cur.fetchall()

# Group by amount
amount_groups = defaultdict(list)
for p in unmatched:
    amt = round(float(p['amount']), 2)
    amount_groups[amt].append(p)

# Find recurring (3+)
recurring = [(amt, pays) for amt, pays in amount_groups.items() if len(pays) >= 3]

print(f"=== RECURRING PAYMENT DETAILS ===\n")
print(f"Found {len(recurring)} amounts occurring 3+ times\n")

for amt, pays in sorted(recurring, key=lambda x: -len(x[1])):
    print(f"Amount: ${amt:,.2f} ({len(pays)} occurrences)")
    print(f"Total: ${amt * len(pays):,.2f}\n")
    
    sorted_pays = sorted(pays, key=lambda p: p['payment_date'])
    
    for i, p in enumerate(sorted_pays, 1):
        print(f"  {i}. Payment {p['payment_id']}: ${float(p['amount']):,.2f} on {p['payment_date']}")
        print(f"     Key: {p['payment_key']}")
        
        if i > 1:
            prev_date = sorted_pays[i-2]['payment_date']
            gap = (p['payment_date'] - prev_date).days
            print(f"     Gap from previous: {gap} days")
    
    # Calculate average gap
    if len(sorted_pays) >= 2:
        dates = [p['payment_date'] for p in sorted_pays]
        gaps = [(dates[i+1] - dates[i]).days for i in range(len(dates)-1)]
        avg_gap = sum(gaps) / len(gaps)
        max_gap = max(gaps)
        min_gap = min(gaps)
        print(f"\n  Date pattern: {min_gap}-{max_gap} days apart (avg: {avg_gap:.1f})")
        
        # Check if it's consistent (loan-like)
        if all(abs(g - avg_gap) <= 4 for g in gaps):
            print(f"  ⚠️  CONSISTENT SPACING - LIKELY AUTOMATED (loan repayment?)")
        else:
            print(f"  ℹ️  Variable spacing - might be legitimate repeat customer")
    
    print()

print("\n=== RECOMMENDATION ===")
total_recurring_amt = sum(amt * len(pays) for amt, pays in recurring)
total_recurring_count = sum(len(pays) for amt, pays in recurring)

print(f"Total recurring payments: {total_recurring_count}")
print(f"Total recurring amount: ${total_recurring_amt:,.2f}")
print(f"\nIf these are Square Capital loan repayments:")
print(f"  → They should be recorded as expenses (loan payments to Square)")
print(f"  → NOT linked to customer charters")
print(f"  → Check Square dashboard for active Capital loans")

cur.close()
conn.close()
