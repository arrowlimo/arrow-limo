#!/usr/bin/env python3
"""Categorize unmatched banking deposits by type and relevance to charters."""
import psycopg2
import os
from datetime import datetime
from collections import defaultdict
import re

DB_HOST = os.environ.get('DB_HOST', 'localhost')
DB_NAME = os.environ.get('DB_NAME', 'almsdata')
DB_USER = os.environ.get('DB_USER', 'postgres')
DB_PASSWORD = os.environ.get('DB_PASSWORD', os.environ.get("DB_PASSWORD"))

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

# Find all unmatched banking deposits
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

# Categorize deposits
categories = {
    'Employee E-Transfer': [],
    'Square Merchant Feed': [],
    'Square POS Payment': [],
    'ATM Cash Deposit': [],
    'MoneyMart Check Cashing': [],
    'Other E-Transfer': [],
    'Other Deposit': [],
}

def categorize(desc):
    """Categorize deposit by description."""
    if not desc:
        return 'Other Deposit'
    
    desc_upper = desc.upper()
    
    # E-transfers with employee/known payment patterns
    if 'E-TRANSFER' in desc_upper and any(name in desc_upper for name in ['AARON', 'PAY', 'EMPLOYEE', 'SALARY', 'REIMBURS']):
        return 'Employee E-Transfer'
    
    # Square merchant deposits (aggregated from POS)
    if 'SQUARE' in desc_upper and ('MISC PAYMENT' in desc_upper or 'DEPOSIT' in desc_upper):
        return 'Square Merchant Feed'
    
    # Square POS customer payments
    if 'SQUARE' in desc_upper and ('POS' in desc_upper or 'CARD' in desc_upper):
        return 'Square POS Payment'
    
    # ATM deposits
    if 'ATM' in desc_upper or 'AUTOMATED BANKING MACHINE' in desc_upper:
        return 'ATM Cash Deposit'
    
    # MoneyMart (check cashing)
    if 'MONEYMART' in desc_upper or 'MONEY MART' in desc_upper:
        return 'MoneyMart Check Cashing'
    
    # Other e-transfers
    if 'E-TRANSFER' in desc_upper or 'ETRANSFER' in desc_upper:
        return 'Other E-Transfer'
    
    # Other deposits
    return 'Other Deposit'

for row in results:
    tid, date, amount, desc, account = row
    category = categorize(desc)
    categories[category].append({
        'id': tid,
        'date': date,
        'amount': amount,
        'desc': desc,
        'account': account
    })

# Display results
print("\n" + "=" * 130)
print("UNMATCHED BANKING DEPOSITS - CATEGORIZED BY TYPE".center(130))
print("=" * 130)

charter_relevant = ['Square POS Payment', 'Other E-Transfer', 'Other Deposit', 'ATM Cash Deposit']
non_charter = ['Employee E-Transfer', 'Square Merchant Feed', 'MoneyMart Check Cashing']

print("\n📋 CHARTER-RELEVANT DEPOSITS (need matching):")
print("-" * 130)

total_charter_relevant = 0
for cat in charter_relevant:
    if categories[cat]:
        items = categories[cat]
        cat_sum = sum(item['amount'] for item in items)
        total_charter_relevant += cat_sum
        
        print(f"\n{cat}: {len(items)} deposits | Total: ${cat_sum:,.2f}")
        print("-" * 130)
        print(f"{'ID':<8} | {'Date':<12} | {'Amount':>12} | {'Account':<10} | {'Description':<80}")
        print("-" * 130)
        
        for item in items[:15]:  # Show first 15
            desc_short = (item['desc'][:77] + '...') if item['desc'] and len(item['desc']) > 80 else (item['desc'] or '')
            acct_short = (item['account'][-4:] if item['account'] else 'N/A')
            print(f"{item['id']:<8} | {str(item['date'])[:10]:<12} | {item['amount']:>12.2f} | {acct_short:<10} | {desc_short:<80}")
        
        if len(items) > 15:
            print(f"... and {len(items) - 15} more in this category")

print("\n\n⏭️  NON-CHARTER DEPOSITS (skip these, handle separately):")
print("-" * 130)

total_non_charter = 0
for cat in non_charter:
    if categories[cat]:
        items = categories[cat]
        cat_sum = sum(item['amount'] for item in items)
        total_non_charter += cat_sum
        
        print(f"\n{cat}: {len(items)} deposits | Total: ${cat_sum:,.2f}")
        print("-" * 130)
        print(f"{'ID':<8} | {'Date':<12} | {'Amount':>12} | {'Account':<10} | {'Description':<80}")
        print("-" * 130)
        
        for item in items[:10]:  # Show first 10
            desc_short = (item['desc'][:77] + '...') if item['desc'] and len(item['desc']) > 80 else (item['desc'] or '')
            acct_short = (item['account'][-4:] if item['account'] else 'N/A')
            print(f"{item['id']:<8} | {str(item['date'])[:10]:<12} | {item['amount']:>12.2f} | {acct_short:<10} | {desc_short:<80}")
        
        if len(items) > 10:
            print(f"... and {len(items) - 10} more in this category")

print("\n\n" + "=" * 130)
print("RECONCILIATION SUMMARY".center(130))
print("=" * 130)
print(f"\nCharter-Relevant Total:    {sum(len(categories[c]) for c in charter_relevant):>6} deposits | ${total_charter_relevant:>12,.2f}")
print(f"Non-Charter Total:          {sum(len(categories[c]) for c in non_charter):>6} deposits | ${total_non_charter:>12,.2f}")
print(f"GRAND TOTAL:               {sum(len(categories[c]) for c in categories):>6} deposits | ${total_charter_relevant + total_non_charter:>12,.2f}")
print("=" * 130)
print("\n✅ FOCUS: Match the Charter-Relevant deposits to payments (expand date window)")
print("⏭️  LATER: Handle employee transfers, Square merchant feeds separately\n")
