#!/usr/bin/env python3
"""
Find all vehicle parts, repairs, and maintenance expenses in banking transactions.
These need to be properly categorized in the GL.
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
print("VEHICLE PARTS, REPAIRS & MAINTENANCE EXPENSE ANALYSIS")
print("=" * 140)

# Define search patterns for vehicle-related expenses
patterns = {
    'Auto Parts Stores': [
        '%canadian tire%',
        '%napa%',
        '%lordco%',
        '%princess auto%',
        '%advance auto%',
        '%autozone%',
        '%auto value%',
        '%carquest%'
    ],
    'Auto Repair Shops': [
        '%erles auto%',
        '%tire garage%',
        '%midas%',
        '%speedy%',
        '%mr. lube%',
        '%jiffy lube%',
        '%fountain tire%',
        '%kal tire%',
        '%active green%',
        '%auto repair%',
        '%automotive%',
        '%mechanic%',
        '%collision%',
        '%body shop%'
    ],
    'Vehicle Dealers/Service': [
        '%heffner%',
        '%honda%',
        '%toyota%',
        '%ford%',
        '%chrysler%',
        '%dodge%',
        '%gm dealer%',
        '%chevrolet%',
        '%nissan%'
    ],
    'Tire Services': [
        '%tire%',
        '%wheel%'
    ],
    'Fuel/Gas': [
        '%fas gas%',
        '%petro%canada%',
        '%shell%',
        '%esso%',
        '%husky%',
        '%co-op gas%',
        '%7-eleven%fuel%',
        '%fuel%',
        '%gasoline%'
    ],
    'Car Washes': [
        '%car wash%',
        '%car care%',
        '%detail%'
    ],
    'Towing': [
        '%tow%',
        '%towing%'
    ],
    'Oil Changes': [
        '%oil change%',
        '%lube%',
        '%quick lube%'
    ],
    'Vehicle Registration/Insurance': [
        '%registry%',
        '%insurance%',
        '%icbc%',
        '%dmv%',
        '%motor vehicle%'
    ]
}

all_results = {}
category_totals = {}

print("\n" + "=" * 140)
print("SEARCHING FOR VEHICLE EXPENSES BY CATEGORY")
print("=" * 140)

for category, search_patterns in patterns.items():
    print(f"\nSearching: {category}...")
    
    # Build OR conditions for all patterns in this category
    conditions = " OR ".join([f"description ILIKE '{pattern}'" for pattern in search_patterns])
    
    query = f"""
        SELECT 
            transaction_id,
            transaction_date,
            description,
            debit_amount,
            credit_amount,
            category,
            vendor_extracted
        FROM banking_transactions
        WHERE ({conditions})
          AND debit_amount > 0
        ORDER BY transaction_date DESC
    """
    
    cur.execute(query)
    results = cur.fetchall()
    
    if results:
        all_results[category] = results
        total = sum(row[3] or Decimal('0') for row in results)
        category_totals[category] = total
        print(f"  Found {len(results)} transactions, Total: ${total:,.2f}")
    else:
        print(f"  No transactions found")

# Display detailed results
print("\n" + "=" * 140)
print("DETAILED BREAKDOWN BY CATEGORY")
print("=" * 140)

grand_total = Decimal('0')

for category in sorted(category_totals.keys(), key=lambda x: category_totals[x], reverse=True):
    results = all_results[category]
    total = category_totals[category]
    grand_total += total
    
    print(f"\n{'=' * 140}")
    print(f"{category.upper()}")
    print(f"{'=' * 140}")
    print(f"Transactions: {len(results)} | Total: ${total:,.2f}\n")
    
    # Group by vendor
    vendors = defaultdict(lambda: {'count': 0, 'total': Decimal('0'), 'transactions': []})
    
    for row in results:
        trans_id, date, desc, debit, credit, cat, vendor = row
        vendor_name = vendor if vendor else desc[:50]
        vendors[vendor_name]['count'] += 1
        vendors[vendor_name]['total'] += debit or Decimal('0')
        vendors[vendor_name]['transactions'].append((date, debit, desc[:80]))
    
    # Show top vendors in this category
    print(f"{'Vendor':<50} {'Count':<8} {'Total':<15}")
    print("-" * 140)
    
    for vendor_name in sorted(vendors.keys(), key=lambda x: vendors[x]['total'], reverse=True)[:10]:
        info = vendors[vendor_name]
        print(f"{vendor_name[:50]:<50} {info['count']:<8} ${info['total']:<14,.2f}")
    
    if len(vendors) > 10:
        remaining_count = sum(v['count'] for k, v in vendors.items() if k not in list(sorted(vendors.keys(), key=lambda x: vendors[x]['total'], reverse=True)[:10]))
        remaining_total = sum(v['total'] for k, v in vendors.items() if k not in list(sorted(vendors.keys(), key=lambda x: vendors[x]['total'], reverse=True)[:10]))
        print(f"{'... and ' + str(len(vendors) - 10) + ' more vendors':<50} {remaining_count:<8} ${remaining_total:<14,.2f}")

# Summary by year
print("\n" + "=" * 140)
print("VEHICLE EXPENSES BY YEAR")
print("=" * 140)

cur.execute("""
    SELECT 
        EXTRACT(YEAR FROM transaction_date) as year,
        COUNT(*) as count,
        SUM(debit_amount) as total
    FROM banking_transactions
    WHERE description ILIKE ANY(ARRAY[
        '%canadian tire%', '%napa%', '%lordco%', '%princess auto%',
        '%erles auto%', '%tire garage%', '%auto repair%', '%automotive%',
        '%heffner%', '%tire%', '%fas gas%', '%petro%', '%shell%', '%esso%',
        '%car wash%', '%tow%', '%oil change%', '%lube%', '%insurance%',
        '%mechanic%', '%collision%', '%body shop%', '%fuel%'
    ])
    AND debit_amount > 0
    GROUP BY EXTRACT(YEAR FROM transaction_date)
    ORDER BY year DESC
""")

year_results = cur.fetchall()

print(f"\n{'Year':<8} {'Transactions':<15} {'Total Spent':<20}")
print("-" * 140)

for year, count, total in year_results:
    if year:
        print(f"{int(year):<8} {count:<15,} ${total or 0:<19,.2f}")

# Grand summary
print("\n" + "=" * 140)
print("OVERALL SUMMARY")
print("=" * 140)

total_transactions = sum(len(results) for results in all_results.values())
print(f"\n  Total vehicle-related transactions found: {total_transactions:,}")
print(f"  Total vehicle expenses: ${grand_total:,.2f}")
print(f"  Average transaction: ${grand_total / total_transactions if total_transactions > 0 else 0:,.2f}")

# Check categorization status
print("\n" + "=" * 140)
print("CATEGORIZATION STATUS")
print("=" * 140)

all_trans = []
for results in all_results.values():
    all_trans.extend(results)

categorized = sum(1 for t in all_trans if t[5])  # t[5] is category
uncategorized = len(all_trans) - categorized

print(f"\n  Categorized: {categorized:,} ({categorized/len(all_trans)*100:.1f}%)")
print(f"  Uncategorized: {uncategorized:,} ({uncategorized/len(all_trans)*100:.1f}%)")

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
print("RECOMMENDED GL ACCOUNTS")
print("=" * 140)
print("""
  Create/use these GL accounts for vehicle expenses:

  5200 - Vehicle Fuel & Gas
    - Fas Gas, Petro-Canada, Shell, Esso, Husky, Co-op
  
  5210 - Vehicle Repairs & Maintenance
    - Erles Auto, The Tire Garage, repair shops, mechanics
  
  5220 - Vehicle Parts & Supplies
    - Canadian Tire, NAPA, Lordco, Princess Auto
  
  5230 - Tires & Wheels
    - Tire purchases and installations
  
  5240 - Oil Changes & Lubrication
    - Mr. Lube, Jiffy Lube, quick lube services
  
  5250 - Vehicle Washing & Detailing
    - Car washes and detailing services
  
  5260 - Towing & Roadside Assistance
    - Towing services
  
  5270 - Vehicle Registration & Licensing
    - Registry, DMV, ICBC fees
  
  5280 - Vehicle Insurance
    - Insurance premiums (may be separate from repairs)
  
  5290 - Vehicle Lease Payments
    - Heffner Auto payments (already tracked: $576,608.28)
""")

print("\n" + "=" * 140)
print("NEXT STEPS")
print("=" * 140)
print("""
  1. Review all identified transactions for accuracy
  2. Categorize uncategorized transactions into appropriate GL accounts
  3. Verify vendor names and correct any misclassifications
  4. Set up recurring vendor rules for auto-categorization
  5. Update accounting records to reflect these expenses
  6. Generate financial reports showing vehicle expense trends
""")

cur.close()
conn.close()

print("\n" + "=" * 140)
print("ANALYSIS COMPLETE")
print("=" * 140)
