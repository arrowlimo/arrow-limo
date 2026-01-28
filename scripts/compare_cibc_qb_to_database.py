#!/usr/bin/env python3
"""
Compare CIBC QuickBooks reconciliation data against banking_transactions database.

Identifies:
- Transactions already in database
- Missing transactions that need import
- Potential duplicates

Created: November 25, 2025
"""

import csv
import psycopg2
import os
from datetime import datetime
from difflib import SequenceMatcher

CSV_PATH = r"l:\limo\data\cibc_qb_reconciliation_consolidated.csv"

conn = psycopg2.connect(
    host=os.getenv('DB_HOST', 'localhost'),
    database=os.getenv('DB_NAME', 'almsdata'),
    user=os.getenv('DB_USER', 'postgres'),
    password=os.getenv('DB_PASSWORD', '***REMOVED***')
)
cur = conn.cursor()

print("\n" + "="*80)
print("CIBC QB RECONCILIATION vs DATABASE COMPARISON")
print("="*80)

# Load CSV transactions
print(f"\n1. Loading CSV file: {CSV_PATH}")
csv_transactions = []

with open(CSV_PATH, 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        csv_transactions.append({
            'date': datetime.strptime(row['date'], '%Y-%m-%d').date(),
            'type': row['type'],
            'num': row['num'],
            'name': row['name'],
            'amount': float(row['amount']),
            'balance': float(row['balance']),
            'pages': row['appears_in_pages'],
            'dup_count': int(row['duplicate_count'])
        })

print(f"   Loaded: {len(csv_transactions)} transactions")
print(f"   Date range: {min(t['date'] for t in csv_transactions)} to {max(t['date'] for t in csv_transactions)}")

# Load database transactions for CIBC account
print(f"\n2. Loading database transactions (account 0228362)...")
cur.execute("""
    SELECT 
        transaction_date,
        description,
        debit_amount,
        credit_amount,
        balance
    FROM banking_transactions
    WHERE account_number = '0228362'
    ORDER BY transaction_date
""")

db_transactions = []
for row in cur.fetchall():
    db_transactions.append({
        'date': row[0],
        'description': row[1],
        'debit': float(row[2]) if row[2] else 0.0,
        'credit': float(row[3]) if row[3] else 0.0,
        'balance': float(row[4]) if row[4] else 0.0
    })

print(f"   Loaded: {len(db_transactions)} transactions")
if db_transactions:
    print(f"   Date range: {min(t['date'] for t in db_transactions)} to {max(t['date'] for t in db_transactions)}")

# Build lookup dictionary for fast matching
print(f"\n3. Building lookup index...")
db_lookup = {}
for db_txn in db_transactions:
    key = (db_txn['date'], abs(db_txn['debit'] - db_txn['credit']))
    if key not in db_lookup:
        db_lookup[key] = []
    db_lookup[key].append(db_txn)

print(f"   Indexed: {len(db_lookup)} unique date+amount combinations")

# Match CSV transactions to database
print(f"\n4. Matching transactions...")
matched = []
unmatched = []

for csv_txn in csv_transactions:
    amount = abs(csv_txn['amount'])
    key = (csv_txn['date'], amount)
    
    if key in db_lookup:
        matched.append(csv_txn)
    else:
        unmatched.append(csv_txn)

print(f"   Matched: {len(matched)} ({len(matched)/len(csv_transactions)*100:.1f}%)")
print(f"   Unmatched: {len(unmatched)} ({len(unmatched)/len(csv_transactions)*100:.1f}%)")

# Analyze unmatched by type
print(f"\n5. Unmatched transactions by type:")
by_type = {}
for txn in unmatched:
    tx_type = txn['type']
    if tx_type not in by_type:
        by_type[tx_type] = {'count': 0, 'total': 0.0}
    by_type[tx_type]['count'] += 1
    by_type[tx_type]['total'] += txn['amount']

for tx_type in sorted(by_type.keys()):
    stats = by_type[tx_type]
    print(f"   {tx_type:30} | {stats['count']:4} txns | ${stats['total']:>12,.2f}")

# Sample unmatched
print(f"\n6. Sample unmatched transactions (first 10):")
print(f"   {'Date':>12} {'Type':>15} {'Amount':>12} {'Name':>40}")
for txn in unmatched[:10]:
    print(f"   {str(txn['date']):>12} {txn['type']:>15} ${txn['amount']:>10.2f} {txn['name'][:40]}")

# Check for date ranges with NO database coverage
print(f"\n7. Checking database coverage by year/month...")
csv_by_month = {}
db_by_month = {}

for txn in csv_transactions:
    key = (txn['date'].year, txn['date'].month)
    csv_by_month[key] = csv_by_month.get(key, 0) + 1

for txn in db_transactions:
    key = (txn['date'].year, txn['date'].month)
    db_by_month[key] = db_by_month.get(key, 0) + 1

print(f"   {'Year-Month':>12} {'CSV':>8} {'Database':>12} {'Gap':>8}")
for year_month in sorted(csv_by_month.keys()):
    csv_count = csv_by_month[year_month]
    db_count = db_by_month.get(year_month, 0)
    gap = csv_count - db_count
    
    year, month = year_month
    status = "✓ OK" if gap <= 0 else f"GAP: {gap}"
    print(f"   {year}-{month:02d}       {csv_count:6} {db_count:12} {status:>8}")

print("\n" + "="*80)
print("SUMMARY")
print("="*80)
print(f"\nCSV (QuickBooks): {len(csv_transactions)} unique transactions")
print(f"Database (CIBC):  {len(db_transactions)} transactions")
print(f"Match rate:       {len(matched)/len(csv_transactions)*100:.1f}%")
print(f"To import:        {len(unmatched)} transactions")

print("\nNEXT STEPS:")
print("1. Review unmatched transactions above")
print("2. Create import script for missing {0} transactions".format(len(unmatched)))
print("3. Verify cheque numbers match")
print("4. Handle date range gaps")

cur.close()
conn.close()
