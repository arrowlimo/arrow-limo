#!/usr/bin/env python3
"""
Opening/Closing Balance Audit for Account 1615
"""

import psycopg2
from decimal import Decimal

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

print("="*80)
print("ACCOUNT 1615 - OPENING/CLOSING BALANCE AUDIT")
print("="*80)

# Get all opening and closing balance entries
cur.execute("""
    SELECT transaction_id, transaction_date, description, 
           debit_amount, credit_amount, balance
    FROM banking_transactions
    WHERE account_number = '1615'
      AND (description LIKE '%pening balance%' OR description LIKE '%losing balance%')
    ORDER BY transaction_date
""")

balance_entries = cur.fetchall()

print(f"\nFound {len(balance_entries)} opening/closing balance entries:")
print(f"\n{'Date':<12} {'Type':<20} {'Debit':<12} {'Credit':<12} {'Balance':<12}")
print("-" * 75)

for row in balance_entries:
    date = row[1]
    desc = row[2]
    debit = f"${row[3]:,.2f}" if row[3] else ""
    credit = f"${row[4]:,.2f}" if row[4] else ""
    balance = f"${row[5]:,.2f}" if row[5] else "NULL"
    print(f"{str(date):<12} {desc:<20} {debit:<12} {credit:<12} {balance:<12}")

# Group by year-month and check opening/closing pairs
print("\n" + "="*80)
print("MONTHLY BALANCE VERIFICATION")
print("="*80)

cur.execute("""
    SELECT 
        TO_CHAR(transaction_date, 'YYYY-MM') as month,
        description,
        balance,
        transaction_date
    FROM banking_transactions
    WHERE account_number = '1615'
      AND (description LIKE '%pening balance%' OR description LIKE '%losing balance%')
    ORDER BY transaction_date
""")

balances_by_month = {}
for row in cur.fetchall():
    month = row[0]
    desc = row[1]
    balance = row[2]
    date = row[3]
    
    if month not in balances_by_month:
        balances_by_month[month] = {'opening': None, 'closing': None, 'opening_date': None, 'closing_date': None}
    
    if 'Opening' in desc or 'opening' in desc:
        balances_by_month[month]['opening'] = balance
        balances_by_month[month]['opening_date'] = date
    elif 'Closing' in desc or 'closing' in desc:
        balances_by_month[month]['closing'] = balance
        balances_by_month[month]['closing_date'] = date

# Check if closing balance of month N = opening balance of month N+1
print(f"\n{'Month':<10} {'Opening':<15} {'Closing':<15} {'Next Opening':<15} {'Match?':<10}")
print("-" * 75)

months_sorted = sorted(balances_by_month.keys())
issues = []

for i, month in enumerate(months_sorted):
    opening = balances_by_month[month]['opening']
    closing = balances_by_month[month]['closing']
    
    next_opening = None
    if i + 1 < len(months_sorted):
        next_month = months_sorted[i + 1]
        next_opening = balances_by_month[next_month]['opening']
    
    opening_str = f"${opening:,.2f}" if opening else "MISSING"
    closing_str = f"${closing:,.2f}" if closing else "MISSING"
    next_opening_str = f"${next_opening:,.2f}" if next_opening else "N/A"
    
    match = ""
    if closing and next_opening:
        if abs(float(closing) - float(next_opening)) < 0.01:
            match = "✅"
        else:
            match = "❌ MISMATCH"
            issues.append(f"{month} closing (${closing:,.2f}) != {months_sorted[i+1]} opening (${next_opening:,.2f})")
    
    print(f"{month:<10} {opening_str:<15} {closing_str:<15} {next_opening_str:<15} {match:<10}")

# Calculate actual balances based on transactions
print("\n" + "="*80)
print("CALCULATED BALANCE VERIFICATION")
print("="*80)

for month in months_sorted:
    month_data = balances_by_month[month]
    opening_date = month_data['opening_date']
    closing_date = month_data['closing_date']
    
    if not opening_date or not closing_date:
        continue
    
    # Get transactions between opening and closing
    cur.execute("""
        SELECT 
            COUNT(*) as txn_count,
            COALESCE(SUM(debit_amount), 0) as total_debits,
            COALESCE(SUM(credit_amount), 0) as total_credits
        FROM banking_transactions
        WHERE account_number = '1615'
          AND transaction_date >= %s
          AND transaction_date <= %s
          AND description NOT LIKE '%%pening balance%%'
          AND description NOT LIKE '%%losing balance%%'
    """, (opening_date, closing_date))
    
    txn_count, total_debits, total_credits = cur.fetchone()
    
    opening_bal = float(month_data['opening'] or 0)
    closing_bal = float(month_data['closing'] or 0)
    
    calculated_closing = opening_bal + float(total_credits) - float(total_debits)
    difference = calculated_closing - closing_bal
    
    print(f"\n{month}:")
    print(f"  Opening Balance: ${opening_bal:,.2f}")
    print(f"  Transactions: {txn_count} (Credits: ${float(total_credits):,.2f}, Debits: ${float(total_debits):,.2f})")
    print(f"  Calculated Closing: ${calculated_closing:,.2f}")
    print(f"  Recorded Closing: ${closing_bal:,.2f}")
    
    if abs(difference) < 0.01:
        print(f"  ✅ MATCH")
    else:
        print(f"  ❌ DIFFERENCE: ${difference:,.2f}")
        issues.append(f"{month}: Calculated ${calculated_closing:,.2f} != Recorded ${closing_bal:,.2f}")

# Summary
print("\n" + "="*80)
print("AUDIT SUMMARY")
print("="*80)

if issues:
    print(f"\n❌ Found {len(issues)} issues:")
    for issue in issues:
        print(f"  • {issue}")
else:
    print(f"\n✅ All opening/closing balances match correctly!")
    print(f"   Total balance entries checked: {len(balance_entries)}")

cur.close()
conn.close()
