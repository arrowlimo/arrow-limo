#!/usr/bin/env python3
"""Categorize remaining 1,145 unmatched e-transfers into groups."""
import psycopg2
import os

DB_HOST = os.environ.get('DB_HOST', 'localhost')
DB_NAME = os.environ.get('DB_NAME', 'almsdata')
DB_USER = os.environ.get('DB_USER', 'postgres')
DB_PASSWORD = os.environ.get('DB_PASSWORD', os.environ.get("DB_PASSWORD"))

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

print("\n" + "=" * 140)
print("CATEGORIZE 1,145 UNMATCHED E-TRANSFERS".center(140))
print("=" * 140)

# Get all unmatched e-transfers
cur.execute('''
    SELECT 
        bt.transaction_id,
        bt.transaction_date,
        bt.credit_amount,
        bt.description
    FROM banking_transactions bt
    WHERE bt.credit_amount > 0
      AND (bt.description ILIKE '%E-TRANSFER%' OR bt.description ILIKE '%ETRANSFER%')
      AND bt.reconciled_payment_id IS NULL
    ORDER BY bt.transaction_date DESC;
''')

unmatched = cur.fetchall()

print(f"\nTotal Unmatched: {len(unmatched)} e-transfers | ${sum(u[2] for u in unmatched):,.2f}\n")

# Categorize
categories = {
    'employee_payments': [],      # PAUL RICHARD, SHERRI RYCKMAN, etc.
    'recent_2026': [],            # From 2026 (potential active bookings)
    'small_amount': [],           # < $100 (likely deposits/retainers)
    'medium_amount': [],          # $100-$500
    'large_amount': [],           # $500-$1000
    'very_large_amount': [],      # > $1000
}

EMPLOYEE_NAMES = ['PAUL RICHARD', 'SHERRI', 'SHERRI RYCKMAN', 'DAVID RICHARD', 'DAVID WILLIAM', 
                  'MICHAEL RICHARD', 'BARB', 'BARBARA', 'JERRY', 'JEANNIE', 'MATTHEW']

for etransfer in unmatched:
    trans_id, trans_date, amount, description = etransfer
    
    is_employee = any(name in description.upper() for name in EMPLOYEE_NAMES)
    is_2026 = trans_date.year == 2026
    
    if is_employee:
        categories['employee_payments'].append(etransfer)
    elif is_2026:
        categories['recent_2026'].append(etransfer)
    elif amount < 100:
        categories['small_amount'].append(etransfer)
    elif amount < 500:
        categories['medium_amount'].append(etransfer)
    elif amount < 1000:
        categories['large_amount'].append(etransfer)
    else:
        categories['very_large_amount'].append(etransfer)

# Display by category
for category_name, category_list in categories.items():
    if not category_list:
        continue
    
    label_map = {
        'employee_payments': '👤 EMPLOYEE PAYMENTS (separate payroll)',
        'recent_2026': '📅 2026 BOOKINGS (recent charters)',
        'small_amount': '💰 SMALL (<$100 deposits/retainers)',
        'medium_amount': '💵 MEDIUM ($100-$500)',
        'large_amount': '💲 LARGE ($500-$1,000)',
        'very_large_amount': '💸 VERY LARGE (>$1,000)',
    }
    
    print("=" * 140)
    print(f"{label_map[category_name]} - {len(category_list)} e-transfers | ${sum(e[2] for e in category_list):,.2f}".ljust(140))
    print("=" * 140)
    print(f"{'Date':<12} | {'Amount':>10} | Description (first 100 chars)")
    print("-" * 140)
    
    for i, etransfer in enumerate(category_list):
        trans_id, trans_date, amount, description = etransfer
        date_str = trans_date.strftime('%Y-%m-%d')
        desc_short = description[:100] if description else 'N/A'
        print(f"{date_str} | ${amount:>9.2f} | {desc_short}")
        
        if i >= 14:  # Show first 15 per category
            if len(category_list) > 15:
                print(f"... and {len(category_list) - 15} more")
            break
    
    print()

# Summary
print("=" * 140)
print("SUMMARY BY CATEGORY:".center(140))
print("=" * 140)
print(f"{'Category':<35} | {'Count':>6} | {'Amount':>14} | {'Percentage'}")
print("-" * 140)

total_amount = sum(u[2] for u in unmatched)
for category_name, category_list in sorted(categories.items(), key=lambda x: sum(e[2] for e in x[1]), reverse=True):
    if not category_list:
        continue
    
    label_map = {
        'employee_payments': 'Employee Payments',
        'recent_2026': '2026 Bookings (Recent)',
        'small_amount': 'Small (<$100)',
        'medium_amount': 'Medium ($100-$500)',
        'large_amount': 'Large ($500-$1K)',
        'very_large_amount': 'Very Large (>$1K)',
    }
    
    cat_amount = sum(e[2] for e in category_list)
    percentage = 100 * cat_amount / total_amount
    print(f"{label_map[category_name]:<35} | {len(category_list):>6} | ${cat_amount:>13,.2f} | {percentage:>5.1f}%")

print("=" * 140)
print("\n💡 RECOMMENDED ACTION BY CATEGORY:\n")

print("1️⃣ EMPLOYEE PAYMENTS:")
print("   → Payroll/reimbursements - separate workflow from customer payments")
print(f"   → {len(categories['employee_payments'])} payments | ${sum(e[2] for e in categories['employee_payments']):,.2f}")
print()

print("2️⃣ 2026 BOOKINGS (Recent Charters):")
print("   → These are current/future bookings - likely need full payment reconciliation")
print(f"   → {len(categories['recent_2026'])} payments | ${sum(e[2] for e in categories['recent_2026']):,.2f}")
print("   → PRIORITY: Match these to 21 open 2026 charters")
print()

print("3️⃣ SMALL DEPOSITS (<$100):")
print("   → Likely retainers, deposits, or partial payments")
print(f"   → {len(categories['small_amount'])} payments | ${sum(e[2] for e in categories['small_amount']):,.2f}")
print()

print("4️⃣ MEDIUM ($100-$500):")
print("   → Standard payment sizes - worth reconciling")
print(f"   → {len(categories['medium_amount'])} payments | ${sum(e[2] for e in categories['medium_amount']):,.2f}")
print()

print("5️⃣ LARGE ($500-$1K):")
print("   → Significant payments - high priority for matching")
print(f"   → {len(categories['large_amount'])} payments | ${sum(e[2] for e in categories['large_amount']):,.2f}")
print()

print("6️⃣ VERY LARGE (>$1K):")
print("   → Premium bookings/groups - critical for reconciliation")
print(f"   → {len(categories['very_large_amount'])} payments | ${sum(e[2] for e in categories['very_large_amount']):,.2f}")

print("\n" + "=" * 140 + "\n")

cur.close()
conn.close()
