#!/usr/bin/env python3
"""
Find all e-transfers involving David Richard to identify loan payments.
- E-transfers FROM David Richard = loan payments TO the business
- E-transfers TO David Richard / davidwr@shaw.ca = loan repayments FROM the business
"""

import psycopg2
from decimal import Decimal

# Connect to database
conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REMOVED***'
)
cur = conn.cursor()

print("=" * 120)
print("DAVID RICHARD E-TRANSFER ANALYSIS - LOAN PAYMENTS")
print("=" * 120)

# Find all transactions mentioning David Richard
cur.execute("""
    SELECT 
        transaction_id,
        transaction_date,
        description,
        debit_amount,
        credit_amount,
        balance,
        category,
        vendor_extracted
    FROM banking_transactions
    WHERE description ILIKE '%david%richard%'
       OR description ILIKE '%davidwr@shaw%'
       OR description ILIKE '%davidrichard%'
    ORDER BY transaction_date
""")

results = cur.fetchall()

print(f"\nFound {len(results)} transactions involving David Richard\n")

# Categorize transactions
payments_from_david = []  # Credits - David paying the business (loan payments)
payments_to_david = []    # Debits - Business paying David (loan repayments)

for row in results:
    trans_id, date, desc, debit, credit, balance, category, vendor = row
    
    # Determine direction based on debit/credit
    if credit and credit > 0:
        payments_from_david.append(row)
    elif debit and debit > 0:
        payments_to_david.append(row)

# Display payments FROM David (loan payments to business)
print("=" * 120)
print("PAYMENTS FROM DAVID RICHARD TO BUSINESS (Loan Payments)")
print("=" * 120)
print(f"\nTotal: {len(payments_from_david)} transactions\n")

if payments_from_david:
    total_from_david = Decimal('0')
    print(f"{'Date':<12} {'Amount':<15} {'Description':<80}")
    print("-" * 120)
    
    for row in payments_from_david:
        trans_id, date, desc, debit, credit, balance, category, vendor = row
        amount = credit or Decimal('0')
        total_from_david += amount
        print(f"{str(date):<12} ${amount:<14,.2f} {desc[:75]}")
    
    print("-" * 120)
    print(f"{'TOTAL FROM DAVID:':<12} ${total_from_david:,.2f}")
else:
    print("  No payments found from David Richard")

# Display payments TO David (loan repayments from business)
print("\n" + "=" * 120)
print("PAYMENTS TO DAVID RICHARD FROM BUSINESS (Loan Repayments)")
print("=" * 120)
print(f"\nTotal: {len(payments_to_david)} transactions\n")

if payments_to_david:
    total_to_david = Decimal('0')
    print(f"{'Date':<12} {'Amount':<15} {'Description':<80}")
    print("-" * 120)
    
    for row in payments_to_david:
        trans_id, date, desc, debit, credit, balance, category, vendor = row
        amount = debit or Decimal('0')
        total_to_david += amount
        print(f"{str(date):<12} ${amount:<14,.2f} {desc[:75]}")
    
    print("-" * 120)
    print(f"{'TOTAL TO DAVID:':<12} ${total_to_david:,.2f}")
else:
    print("  No payments found to David Richard")

# Summary
print("\n" + "=" * 120)
print("LOAN ACCOUNT SUMMARY")
print("=" * 120)

total_from = sum(row[4] or Decimal('0') for row in payments_from_david)
total_to = sum(row[3] or Decimal('0') for row in payments_to_david)
net_position = total_from - total_to

print(f"\n  Loan payments FROM David (money in):     ${total_from:>15,.2f}")
print(f"  Loan repayments TO David (money out):    ${total_to:>15,.2f}")
print(f"  " + "-" * 50)
print(f"  NET POSITION (positive = owed to David): ${net_position:>15,.2f}")

if net_position > 0:
    print(f"\n  ➜ Business owes David Richard: ${net_position:,.2f}")
elif net_position < 0:
    print(f"\n  ➜ David Richard owes business: ${abs(net_position):,.2f}")
else:
    print(f"\n  ➜ Loan account is balanced (paid in full)")

# Check if these are categorized in GL
print("\n" + "=" * 120)
print("CATEGORIZATION CHECK")
print("=" * 120)

categorized_count = sum(1 for row in results if row[6])  # row[6] is category
print(f"\n  Total transactions: {len(results)}")
print(f"  Categorized: {categorized_count}")
print(f"  Uncategorized: {len(results) - categorized_count}")

if categorized_count > 0:
    print("\n  Categories found:")
    categories = {}
    for row in results:
        cat = row[6]
        if cat:
            categories[cat] = categories.get(cat, 0) + 1
    for cat, count in sorted(categories.items()):
        print(f"    - {cat}: {count} transactions")

print("\n" + "=" * 120)
print("RECOMMENDATIONS")
print("=" * 120)
print("""
  1. Tag all payments FROM David Richard as: "Loan Payable - David Richard" (Liability)
  2. Tag all payments TO David Richard as: "Loan Repayment - David Richard" (reduces Liability)
  3. Create GL account: "2100 - Loan Payable - David Richard" if not exists
  4. Verify net loan balance matches David's records
  5. Document loan terms (interest rate, repayment schedule, etc.)
""")

cur.close()
conn.close()

print("=" * 120)
print("ANALYSIS COMPLETE")
print("=" * 120)
