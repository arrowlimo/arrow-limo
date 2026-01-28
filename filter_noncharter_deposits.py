#!/usr/bin/env python3
"""Filter out non-charter-related deposits (fees, insurance, loans, transfers, food/bev, etc.)"""
import psycopg2
import os

DB_HOST = os.environ.get('DB_HOST', 'localhost')
DB_NAME = os.environ.get('DB_NAME', 'almsdata')
DB_USER = os.environ.get('DB_USER', 'postgres')
DB_PASSWORD = os.environ.get('DB_PASSWORD', os.environ.get("DB_PASSWORD"))

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

# Find unmatched "Other Deposits" (not E-transfer, not Square, not ATM)
query = '''
SELECT 
    bt.transaction_id,
    bt.transaction_date,
    bt.credit_amount,
    bt.description,
    bt.account_number
FROM banking_transactions bt
WHERE bt.credit_amount > 0
  AND bt.description NOT ILIKE '%E-TRANSFER%'
  AND bt.description NOT ILIKE '%SQUARE%'
  AND bt.description NOT ILIKE '%ATM%'
  AND bt.description NOT ILIKE '%AUTOMATED BANKING%'
  AND bt.description NOT ILIKE '%MONEY MART%'
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

# Exclude keywords
exclude_keywords = {
    'BANK': 'Bank Transfer/Fee',
    'TRANSFER': 'Bank Transfer',
    'DEPOSIT IBB': 'Internal Bank Transfer',
    'DEPOSIT INTERAC': 'Internal Transfer',
    'FEE': 'Bank Fee',
    'SERVICE CHARGE': 'Service Charge',
    'INSURANCE': 'Insurance',
    'LOAN': 'Loan',
    'CREDIT MEMO': 'Credit/Adjustment',
    'ADJUSTMENT': 'Adjustment',
    'INTEREST': 'Interest',
    'DIVIDEND': 'Dividend',
    'FOOD': 'Food & Beverage',
    'BEVERAGE': 'Food & Beverage',
    'RESTAURANT': 'Food & Beverage',
    'MEAL': 'Food & Beverage',
    'COFFEE': 'Food & Beverage',
    'PIZZA': 'Food & Beverage',
    'MCDONALD': 'Food & Beverage',
    'UBER': 'Uber/Delivery',
    'SKIP': 'Skip/Delivery',
    'DOORSTEP': 'Delivery Service',
    'HOTEL': 'Travel/Hotel',
    'AIRLINE': 'Travel',
    'MOTEL': 'Travel',
    'PARKING': 'Parking',
    'GAS STATION': 'Fuel',
    'SHELL': 'Fuel',
    'PETRO': 'Fuel',
    'CO-OP': 'Fuel',
    'CIRCLE K': 'Fuel',
    'GROCERY': 'Groceries',
    'SUPERMARKET': 'Groceries',
    'WALMART': 'Retail',
    'COSTCO': 'Retail',
    'BEST BUY': 'Retail',
    'AMAZON': 'Online Retail',
    'PAYROLL': 'Payroll',
    'SALARY': 'Payroll',
    'WAGES': 'Payroll',
    'WCB': 'WCB Insurance',
    'WORKERS COMP': 'WCB Insurance',
    'TAX': 'Tax Payment',
    'REVENUE': 'Tax/CRA',
    'CRA': 'CRA Tax',
    'GST': 'GST Refund/Payment',
    'UTILITY': 'Utilities',
    'POWER': 'Utilities',
    'WATER': 'Utilities',
    'GAS BILL': 'Utilities',
    'PHONE': 'Communications',
    'INTERNET': 'Communications',
    'CELLULAR': 'Communications',
    'RENT': 'Rent/Lease',
    'LEASE': 'Rent/Lease',
    'MORTGAGE': 'Mortgage',
    'PROPERTY TAX': 'Property Tax',
    'SUBSCRIPTION': 'Subscription',
    'MEMBERSHIP': 'Membership Fee',
}

# Categorize
excluded = []
charter_relevant = []

for row in results:
    tid, date, amount, desc, account = row
    
    excluded_reason = None
    for keyword, reason in exclude_keywords.items():
        if keyword in desc.upper():
            excluded_reason = reason
            break
    
    if excluded_reason:
        excluded.append((tid, date, amount, desc, excluded_reason))
    else:
        charter_relevant.append((tid, date, amount, desc))

# Display
print("\n" + "=" * 160)
print("DEPOSIT FILTERING: NON-CHARTER vs CHARTER-RELEVANT".center(160))
print("=" * 160)

print(f"\n❌ EXCLUDED (Non-Charter): {len(excluded)} deposits | ${sum(x[2] for x in excluded):,.2f}")
print("-" * 160)

# Group by reason
reasons = {}
for tid, date, amount, desc, reason in excluded:
    if reason not in reasons:
        reasons[reason] = {'count': 0, 'total': 0, 'items': []}
    reasons[reason]['count'] += 1
    reasons[reason]['total'] += amount
    reasons[reason]['items'].append((date, amount, desc))

for reason in sorted(reasons.keys()):
    data = reasons[reason]
    print(f"\n  {reason}: {data['count']} | ${data['total']:,.2f}")
    for date, amount, desc in data['items'][:5]:
        desc_short = (desc[:120] + '...') if len(desc) > 120 else desc
        print(f"    [{str(date)[:10]}] ${amount:>10.2f}  {desc_short}")
    if len(data['items']) > 5:
        print(f"    ... and {len(data['items']) - 5} more")

print(f"\n\n✅ CHARTER-RELEVANT (need matching): {len(charter_relevant)} deposits | ${sum(x[2] for x in charter_relevant):,.2f}")
print("-" * 160)
print(f"{'Date':<12} | {'Amount':>12} | {'Description':<130}")
print("-" * 160)
for tid, date, amount, desc in charter_relevant[:50]:
    desc_short = (desc[:127] + '...') if len(desc) > 130 else desc
    print(f"{str(date)[:10]:<12} | {amount:>12.2f} | {desc_short:<130}")
if len(charter_relevant) > 50:
    print(f"... and {len(charter_relevant) - 50} more")

print("\n\n" + "=" * 160)
print("SUMMARY")
print("=" * 160)
excluded_total = sum(x[2] for x in excluded)
charter_total = sum(x[2] for x in charter_relevant)
print(f"Excluded (non-charter):     {len(excluded):>6} deposits | ${excluded_total:>12,.2f}")
print(f"Charter-Relevant:           {len(charter_relevant):>6} deposits | ${charter_total:>12,.2f}")
print(f"TOTAL OTHER DEPOSITS:       {len(excluded) + len(charter_relevant):>6} deposits | ${excluded_total + charter_total:>12,.2f}")
print("=" * 160 + "\n")
