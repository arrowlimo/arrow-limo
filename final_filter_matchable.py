#!/usr/bin/env python3
"""Filter out ATM, NSF, and check deposits - focus only on matchable customer deposits."""
import psycopg2
import os

DB_HOST = os.environ.get('DB_HOST', 'localhost')
DB_NAME = os.environ.get('DB_NAME', 'almsdata')
DB_USER = os.environ.get('DB_USER', 'postgres')
DB_PASSWORD = os.environ.get('DB_PASSWORD', '***REMOVED***')

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

# Get charter-relevant deposits (exclude E-transfers, Square, ATM already in prior filters)
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
  AND bt.description NOT ILIKE '%BANK%'
  AND bt.description NOT ILIKE '%TRANSFER%'
  AND bt.description NOT ILIKE '%FEE%'
  AND bt.description NOT ILIKE '%SERVICE CHARGE%'
  AND bt.description NOT ILIKE '%INSURANCE%'
  AND bt.description NOT ILIKE '%LOAN%'
  AND bt.description NOT ILIKE '%CREDIT MEMO%'
  AND bt.description NOT ILIKE '%ADJUSTMENT%'
  AND bt.description NOT ILIKE '%INTEREST%'
  AND bt.description NOT ILIKE '%DIVIDEND%'
  AND bt.description NOT ILIKE '%FOOD%'
  AND bt.description NOT ILIKE '%BEVERAGE%'
  AND bt.description NOT ILIKE '%RESTAURANT%'
  AND bt.description NOT ILIKE '%UBER%'
  AND bt.description NOT ILIKE '%HOTEL%'
  AND bt.description NOT ILIKE '%PARKING%'
  AND bt.description NOT ILIKE '%UTILITY%'
  AND bt.description NOT ILIKE '%RENT%'
  AND bt.description NOT ILIKE '%LEASE%'
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

# Exclude NSF and physical deposits
excluded = []
matchable = []

for row in results:
    tid, date, amount, desc, account = row
    
    is_nsf = 'NSF' in desc.upper() or 'NON SUFFICIENT' in desc.upper()
    is_check = 'CHECK' in desc.upper() or 'CHEQUE' in desc.upper()
    is_atm = 'ATM' in desc.upper() or 'DEPOSIT' in desc.upper()
    is_reversal = 'REVERSAL' in desc.upper() or 'DEBIT REVERSAL' in desc.upper()
    
    if is_nsf:
        excluded.append((tid, date, amount, desc, 'NSF - Never Paid'))
    elif is_check and not is_reversal:
        excluded.append((tid, date, amount, desc, 'Physical Check Deposit'))
    elif is_atm and not is_reversal and not 'DEBIT' in desc.upper():
        excluded.append((tid, date, amount, desc, 'ATM Cash Deposit'))
    else:
        matchable.append((tid, date, amount, desc))

# Display
print("\n" + "=" * 160)
print("FINAL FILTERING: ATM/NSF/CHECKS vs MATCHABLE DEPOSITS".center(160))
print("=" * 160)

print(f"\n❌ EXCLUDED (ATM/NSF/Physical Checks): {len(excluded)} deposits | ${sum(x[2] for x in excluded):,.2f}")
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
    for date, amount, desc in data['items'][:8]:
        desc_short = (desc[:120] + '...') if len(desc) > 120 else desc
        print(f"    [{str(date)[:10]}] ${amount:>10.2f}  {desc_short}")
    if len(data['items']) > 8:
        print(f"    ... and {len(data['items']) - 8} more")

print(f"\n\n✅ MATCHABLE TO CHARTERS: {len(matchable)} deposits | ${sum(x[2] for x in matchable):,.2f}")
print("-" * 160)
print(f"{'Date':<12} | {'Amount':>12} | {'Description':<130}")
print("-" * 160)
for tid, date, amount, desc in matchable[:60]:
    desc_short = (desc[:127] + '...') if len(desc) > 130 else desc
    print(f"{str(date)[:10]:<12} | {amount:>12.2f} | {desc_short:<130}")
if len(matchable) > 60:
    print(f"... and {len(matchable) - 60} more")

print("\n\n" + "=" * 160)
print("SUMMARY - RECONCILIATION FOCUS")
print("=" * 160)
excluded_total = sum(x[2] for x in excluded)
matchable_total = sum(x[2] for x in matchable)
print(f"Excluded (NSF/ATM/Checks):  {len(excluded):>6} deposits | ${excluded_total:>12,.2f} | (Handle separately)")
print(f"Matchable to Charters:      {len(matchable):>6} deposits | ${matchable_total:>12,.2f} | (RUN MATCHING NOW)")
print(f"TOTAL OTHER DEPOSITS:       {len(excluded) + len(matchable):>6} deposits | ${excluded_total + matchable_total:>12,.2f}")
print("=" * 160 + "\n")
