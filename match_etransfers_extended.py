#!/usr/bin/env python3
"""Match E-transfers to charters with EXPANDED time window (up to 365 days)."""
import psycopg2
import os
from datetime import datetime

DB_HOST = os.environ.get('DB_HOST', 'localhost')
DB_NAME = os.environ.get('DB_NAME', 'almsdata')
DB_USER = os.environ.get('DB_USER', 'postgres')
DB_PASSWORD = os.environ.get('DB_PASSWORD', '***REMOVED***')

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

# Find all unmatched E-transfers (customer + employee, exclude Square)
query = '''
SELECT 
    bt.transaction_id,
    bt.transaction_date,
    bt.credit_amount,
    bt.description,
    bt.account_number
FROM banking_transactions bt
WHERE bt.credit_amount > 0
  AND (bt.description ILIKE '%E-TRANSFER%' OR bt.description ILIKE '%ETRANSFER%')
  AND NOT EXISTS (
    SELECT 1 FROM payments p 
    WHERE ABS(p.amount - bt.credit_amount) < 0.01
      AND p.payment_date::date >= bt.transaction_date::date - INTERVAL '365 days'
      AND p.payment_date::date <= bt.transaction_date::date + INTERVAL '365 days'
  )
ORDER BY bt.transaction_date DESC, bt.credit_amount DESC;
'''

cur.execute(query)
unmatched_etransfers = cur.fetchall()

# Find E-transfers with matches within ±365 days (but ±7 days not matched)
match_query = '''
SELECT 
    bt.transaction_id,
    bt.transaction_date,
    bt.credit_amount,
    bt.description,
    p.payment_id,
    p.payment_date,
    p.amount,
    p.reserve_number,
    (p.payment_date::date - bt.transaction_date::date) as days_diff,
    ABS(p.amount - bt.credit_amount) as amount_diff
FROM banking_transactions bt
LEFT JOIN payments p ON 
    ABS(p.amount - bt.credit_amount) <= 1.00
    AND p.payment_date::date >= bt.transaction_date::date - INTERVAL '365 days'
    AND p.payment_date::date <= bt.transaction_date::date + INTERVAL '365 days'
WHERE bt.credit_amount > 0
  AND (bt.description ILIKE '%E-TRANSFER%' OR bt.description ILIKE '%ETRANSFER%')
  AND NOT (
    p.payment_date::date >= bt.transaction_date::date - INTERVAL '7 days'
    AND p.payment_date::date <= bt.transaction_date::date + INTERVAL '7 days'
    AND ABS(p.amount - bt.credit_amount) < 0.01
  )
ORDER BY bt.transaction_date DESC, bt.credit_amount DESC;
'''

cur.execute(match_query)
matches = cur.fetchall()
cur.close()
conn.close()

# Categorize known employees
employee_keywords = [
    'BARB PEACOCK',
    'DAVID WILLIAM RICHARD',
    'DAVIDRICHARD',
    'DAVID RICHARD',
    'MATTHEW RICHARD',
    'PAUL RICHARD',
]

# Process matches
matched_extended = []
unmatched_extended = []

for row in matches:
    if row[4] is None:  # No match found
        unmatched_extended.append(row[:4])
    else:
        matched_extended.append(row)

# Display
print("\n" + "=" * 180)
print("E-TRANSFER MATCHING WITH EXTENDED TIME WINDOW (±365 days)".center(180))
print("=" * 180)

print(f"\n✅ MATCHED (7-day to 365-day window): {len([m for m in matched_extended if m[4] is not None])} transfers")
print("-" * 180)
print(f"{'Bank Date':<12} | {'Amount':>10} | {'Payment Date':<12} | {'Days':>5} | {'Reserve':>8} | {'Amount Diff':>10} | {'Description':<80}")
print("-" * 180)

for row in sorted([m for m in matched_extended if m[4] is not None], 
                  key=lambda x: abs(int(x[8])), reverse=True)[:30]:
    bank_date = str(row[1])[:10]
    bank_amt = row[2]
    pay_date = str(row[5])[:10]
    days_diff = int(x[8]) if x[8] else 0
    reserve = row[7] or 'N/A'
    amt_diff = row[9]
    desc_short = (row[3][:77] + '...') if len(row[3]) > 80 else row[3]
    print(f"{bank_date:<12} | {bank_amt:>10.2f} | {pay_date:<12} | {days_diff:>5} | {reserve:>8} | {amt_diff:>10.2f} | {desc_short:<80}")

print(f"\n\n❌ UNMATCHED (no match even in ±365 days): {len(unmatched_extended)} transfers | ${sum(x[2] for x in unmatched_extended):,.2f}")
print("-" * 180)
print(f"{'Bank Date':<12} | {'Amount':>12} | {'Description':<150}")
print("-" * 180)

# Separate employee vs customer
employee_unmatched = []
customer_unmatched = []

for row in unmatched_extended:
    is_employee = False
    for emp_key in employee_keywords:
        if emp_key in row[3].upper():
            is_employee = True
            break
    
    if is_employee:
        employee_unmatched.append(row)
    else:
        customer_unmatched.append(row)

print(f"\nCUSTOMER E-TRANSFERS (Unmatched): {len(customer_unmatched)}")
for row in customer_unmatched[:30]:
    date_str = str(row[1])[:10]
    desc_short = (row[3][:147] + '...') if len(row[3]) > 150 else row[3]
    print(f"{date_str:<12} | {row[2]:>12.2f} | {desc_short:<150}")

print(f"\n\nEMPLOYEE E-TRANSFERS (Unmatched): {len(employee_unmatched)}")
for row in employee_unmatched[:20]:
    date_str = str(row[1])[:10]
    desc_short = (row[3][:147] + '...') if len(row[3]) > 150 else row[3]
    print(f"{date_str:<12} | {row[2]:>12.2f} | {desc_short:<150}")

print("\n\n" + "=" * 180)
print("RECONCILIATION INSIGHT")
print("=" * 180)
print(f"E-Transfer matches (7-365 days):    {len([m for m in matched_extended if m[4] is not None]):>6} transfers")
print(f"E-Transfer unmatched (even 365 days): {len(unmatched_extended):>6} transfers | ${sum(x[2] for x in unmatched_extended):>12,.2f}")
print(f"  - Customer E-Transfers:             {len(customer_unmatched):>6} | ${sum(x[2] for x in customer_unmatched):>12,.2f}")
print(f"  - Employee E-Transfers:             {len(employee_unmatched):>6} | ${sum(x[2] for x in employee_unmatched):>12,.2f}")
print("=" * 180 + "\n")
