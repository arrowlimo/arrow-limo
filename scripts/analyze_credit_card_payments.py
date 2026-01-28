#!/usr/bin/env python3
"""
Find all credit card payments for:
- Royal Bank credit cards
- Canadian Tire Mastercard
- Amazon Visa

These payments represent reimbursement for parts/repairs/expenses purchased on credit cards.
"""

import psycopg2
from decimal import Decimal
from collections import defaultdict

# Connect to database
conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REMOVED***'
)
cur = conn.cursor()

print("=" * 140)
print("CREDIT CARD PAYMENT ANALYSIS - Vehicle Parts & Repairs")
print("=" * 140)
print("\nSearching for payments to:")
print("  - Royal Bank credit cards")
print("  - Canadian Tire Mastercard")
print("  - Amazon Visa")
print("\n" + "=" * 140)

# Search for credit card payments
credit_cards = {
    'Royal Bank Credit Cards': [
        '%royal bank%',
        '%rbc%',
        '%royal%credit%',
        '%rbc%credit%',
        '%rbc%visa%',
        '%rbc%mastercard%'
    ],
    'Canadian Tire Mastercard': [
        '%canadian tire%',
        '%cdn tire%',
        '%ct mastercard%',
        '%triangle%mastercard%'
    ],
    'Amazon Visa': [
        '%amazon%',
        '%amzn%',
        '%amazon%visa%'
    ]
}

all_results = {}
category_totals = {}

print("\nSEARCHING BANKING TRANSACTIONS...")
print("=" * 140)

for card_name, patterns in credit_cards.items():
    print(f"\nSearching: {card_name}...")
    
    # Build OR conditions
    conditions = " OR ".join([f"description ILIKE '{pattern}'" for pattern in patterns])
    
    query = f"""
        SELECT 
            transaction_id,
            transaction_date,
            description,
            debit_amount,
            credit_amount,
            category,
            vendor_extracted,
            balance
        FROM banking_transactions
        WHERE ({conditions})
        ORDER BY transaction_date DESC
    """
    
    cur.execute(query)
    results = cur.fetchall()
    
    if results:
        all_results[card_name] = results
        # Sum debits (payments TO credit card)
        total_debits = sum(row[3] or Decimal('0') for row in results)
        # Sum credits (refunds FROM credit card)
        total_credits = sum(row[4] or Decimal('0') for row in results)
        category_totals[card_name] = {'debits': total_debits, 'credits': total_credits, 'net': total_debits - total_credits}
        
        print(f"  Found {len(results)} transactions")
        print(f"    Payments TO card (debits): ${total_debits:,.2f}")
        print(f"    Refunds FROM card (credits): ${total_credits:,.2f}")
        print(f"    Net payments: ${total_debits - total_credits:,.2f}")
    else:
        print(f"  No transactions found")

# Detailed breakdown
print("\n" + "=" * 140)
print("DETAILED CREDIT CARD PAYMENT BREAKDOWN")
print("=" * 140)

grand_total_debits = Decimal('0')
grand_total_credits = Decimal('0')

for card_name in all_results.keys():
    results = all_results[card_name]
    totals = category_totals[card_name]
    
    print(f"\n{'=' * 140}")
    print(f"{card_name.upper()}")
    print(f"{'=' * 140}")
    print(f"Total Transactions: {len(results)}")
    print(f"Total Payments: ${totals['debits']:,.2f}")
    print(f"Total Refunds: ${totals['credits']:,.2f}")
    print(f"Net Paid: ${totals['net']:,.2f}\n")
    
    grand_total_debits += totals['debits']
    grand_total_credits += totals['credits']
    
    # Show recent transactions
    print(f"{'Date':<12} {'Type':<8} {'Amount':<15} {'Description':<80}")
    print("-" * 140)
    
    for row in results[:20]:  # Show first 20
        trans_id, date, desc, debit, credit, cat, vendor, balance = row
        amount = debit if debit else credit
        trans_type = "Payment" if debit else "Refund"
        print(f"{str(date):<12} {trans_type:<8} ${amount or 0:<14,.2f} {desc[:75]}")
    
    if len(results) > 20:
        print(f"\n  ... and {len(results) - 20} more transactions")
    
    # Payment frequency by year
    print(f"\n  Payments by Year:")
    by_year = defaultdict(lambda: {'count': 0, 'debits': Decimal('0'), 'credits': Decimal('0')})
    
    for row in results:
        year = row[1].year if row[1] else None
        if year:
            by_year[year]['count'] += 1
            by_year[year]['debits'] += row[3] or Decimal('0')
            by_year[year]['credits'] += row[4] or Decimal('0')
    
    for year in sorted(by_year.keys(), reverse=True):
        info = by_year[year]
        net = info['debits'] - info['credits']
        print(f"    {year}: {info['count']:3} transactions, ${net:,.2f} net paid")

# Summary
print("\n" + "=" * 140)
print("OVERALL CREDIT CARD SUMMARY")
print("=" * 140)

total_transactions = sum(len(results) for results in all_results.values())
net_total = grand_total_debits - grand_total_credits

print(f"\n  Total credit card transactions: {total_transactions:,}")
print(f"  Total payments TO credit cards: ${grand_total_debits:,.2f}")
print(f"  Total refunds FROM credit cards: ${grand_total_credits:,.2f}")
print(f"  Net amount paid: ${net_total:,.2f}")

if total_transactions > 0:
    print(f"  Average payment: ${grand_total_debits / total_transactions:,.2f}")

# Check categorization
print("\n" + "=" * 140)
print("CATEGORIZATION STATUS")
print("=" * 140)

all_trans = []
for results in all_results.values():
    all_trans.extend(results)

categorized = sum(1 for t in all_trans if t[5])  # t[5] is category
uncategorized = len(all_trans) - categorized

print(f"\n  Categorized: {categorized:,} ({categorized/len(all_trans)*100:.1f}% if len(all_trans) > 0 else 0)")
print(f"  Uncategorized: {uncategorized:,} ({uncategorized/len(all_trans)*100:.1f}% if len(all_trans) > 0 else 0)")

if categorized > 0:
    print("\n  Current categories used:")
    categories = defaultdict(int)
    for t in all_trans:
        if t[5]:
            categories[t[5]] += 1
    
    for cat, count in sorted(categories.items(), key=lambda x: x[1], reverse=True):
        print(f"    - {cat}: {count} transactions")

# Recommendations
print("\n" + "=" * 140)
print("ACCOUNTING RECOMMENDATIONS")
print("=" * 140)
print("""
  ISSUE: Credit card payments in banking records don't show WHAT was purchased.
  
  The banking transactions show:
    "Payment to Canadian Tire Mastercard - $500"
  
  But they DON'T show:
    - $200 for brake pads
    - $150 for oil filters
    - $150 for cleaning supplies
  
  SOLUTION: You need to track credit card statements separately!
  
  1. OBTAIN CREDIT CARD STATEMENTS:
     ✓ Royal Bank credit card statements (PDF or CSV)
     ✓ Canadian Tire Mastercard statements
     ✓ Amazon Visa statements
  
  2. IMPORT CREDIT CARD TRANSACTIONS:
     Create tables:
     - credit_card_transactions_royal_bank
     - credit_card_transactions_ct_mastercard
     - credit_card_transactions_amazon_visa
     
     Columns needed:
     - transaction_date
     - posted_date
     - merchant_name
     - description
     - amount
     - category (auto parts, fuel, repairs, supplies, etc.)
  
  3. RECONCILE:
     Match credit card payments in banking_transactions to:
     - Credit card statement balances
     - Statement payment due dates
  
  4. CATEGORIZE ACTUAL PURCHASES:
     Instead of "Payment to Canadian Tire - $500"
     You'll have:
     - Brake pads - NAPA - $200 → GL 5220 Vehicle Parts
     - Oil filters - Canadian Tire - $150 → GL 5220 Vehicle Parts
     - Cleaning supplies - Canadian Tire - $150 → GL 5300 Shop Supplies
  
  5. GL ACCOUNT STRUCTURE:
     
     ASSET ACCOUNTS (Credit Cards = Assets when you have credit):
     1200 - Royal Bank Credit Card
     1210 - Canadian Tire Mastercard
     1220 - Amazon Visa
     
     When you pay the credit card:
       Debit: 1200 - Royal Bank Credit Card (reduces asset/increases liability)
       Credit: Bank Account
     
     When you purchase something on credit card:
       Debit: 5220 - Vehicle Parts (expense)
       Credit: 1200 - Royal Bank Credit Card (liability)
""")

print("\n" + "=" * 140)
print("NEXT STEPS - ACTION REQUIRED")
print("=" * 140)
print("""
  IMMEDIATE:
  1. ⬜ Gather all credit card statements (2017-2025)
     - Royal Bank: Download from online banking
     - Canadian Tire: Download from Triangle account
     - Amazon Visa: Download from Chase/Amazon account
  
  2. ⬜ Create credit card import scripts
     - Parse PDF or CSV statements
     - Import individual transactions
     - Categorize by merchant/description
  
  3. ⬜ Set up credit card GL accounts
     - Create liability accounts for each card
     - Record opening balances
     - Track current balances
  
  4. ⬜ Reconcile credit card payments
     - Match banking payment transactions to statement balances
     - Identify any missing payments
     - Document payment dates vs statement dates
  
  5. ⬜ Categorize credit card purchases
     - Vehicle parts → GL 5220
     - Fuel → GL 5200
     - Repairs → GL 5210
     - Amazon supplies → appropriate expense accounts
  
  SHORT-TERM:
  6. ⬜ Generate expense reports by category
     - Total spent on parts vs repairs vs fuel
     - Trend analysis by year/month
     - Vendor analysis
  
  7. ⬜ Set up monthly reconciliation process
     - Reconcile each credit card monthly
     - Ensure all purchases are categorized
     - Track rewards/cash back earned
  
  8. ⬜ Document credit card management policy
     - Which cards for which purposes
     - Approval process for purchases
     - Receipt retention requirements
""")

print("\n" + "=" * 140)
print("IMPORTANT NOTE")
print("=" * 140)
print("""
  The banking transactions show you PAID the credit cards ${:,.2f}
  
  But we DON'T KNOW what you bought with those credit cards!
  
  You need the credit card statements to see the actual itemized purchases:
  - What parts did you buy?
  - What repairs were paid for?
  - What supplies were ordered from Amazon?
  - Where did you fuel up?
  
  Without credit card statements, we can only see:
  "Paid Canadian Tire $500" 
  
  NOT:
  "Bought brake pads $200, oil $50, air filter $75, shop rags $175"
  
  → GET THE CREDIT CARD STATEMENTS! ←
""".format(net_total))

cur.close()
conn.close()

print("\n" + "=" * 140)
print("ANALYSIS COMPLETE")
print("=" * 140)
