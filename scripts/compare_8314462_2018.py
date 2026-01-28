#!/usr/bin/env python3
"""Compare CIBC account 8314462 2018 CSV against database."""

import csv
import psycopg2
from decimal import Decimal
from datetime import datetime
from collections import defaultdict

# Database connection
conn = psycopg2.connect(
    host="localhost",
    database="almsdata",
    user="postgres",
    password="***REMOVED***"
)

# Read CSV file
csv_path = r"L:\limo\CIBC UPLOADS\8314462 (CIBC vehicle loans)\cibc 4462 2018.csv"
csv_transactions = []

print("=" * 80)
print("READING CSV FILE...")
print("=" * 80)

with open(csv_path, 'r', encoding='utf-8') as f:
    reader = csv.reader(f)
    for row in reader:
        if len(row) >= 3:
            date_str = row[0].strip()
            description = row[1].strip()
            debit = row[2].strip() if len(row) > 2 else ""
            credit = row[3].strip() if len(row) > 3 else ""
            
            # Parse date
            try:
                txn_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            except:
                print(f"⚠️  Skipping invalid date: {date_str}")
                continue
            
            # Get amount (absolute value)
            amount = Decimal(debit) if debit else (Decimal(credit) if credit else Decimal(0))
            
            csv_transactions.append({
                'date': txn_date,
                'description': description,
                'debit': Decimal(debit) if debit else Decimal(0),
                'credit': Decimal(credit) if credit else Decimal(0),
                'amount': amount
            })

print(f"✓ Read {len(csv_transactions)} transactions from CSV")
print(f"  Date range: {min(t['date'] for t in csv_transactions)} to {max(t['date'] for t in csv_transactions)}")

# Read database transactions
print("\n" + "=" * 80)
print("READING DATABASE TRANSACTIONS...")
print("=" * 80)

cur = conn.cursor()
cur.execute("""
    SELECT transaction_id, transaction_date, description, debit_amount, credit_amount
    FROM banking_transactions
    WHERE account_number = '8314462'
      AND EXTRACT(YEAR FROM transaction_date) = 2018
    ORDER BY transaction_date
""")

db_transactions = []
for row in cur.fetchall():
    txn_id, txn_date, description, debit, credit = row
    amount = debit if debit else (credit if credit else Decimal(0))
    db_transactions.append({
        'id': txn_id,
        'date': txn_date,
        'description': description,
        'debit': debit if debit else Decimal(0),
        'credit': credit if credit else Decimal(0),
        'amount': amount
    })

print(f"✓ Read {len(db_transactions)} transactions from database")
if db_transactions:
    print(f"  Date range: {min(t['date'] for t in db_transactions)} to {max(t['date'] for t in db_transactions)}")

# Compare by date
print("\n" + "=" * 80)
print("COMPARING BY DATE...")
print("=" * 80)

csv_by_date = defaultdict(list)
for txn in csv_transactions:
    csv_by_date[txn['date']].append(txn)

db_by_date = defaultdict(list)
for txn in db_transactions:
    db_by_date[txn['date']].append(txn)

# Get all dates
all_dates = sorted(set(list(csv_by_date.keys()) + list(db_by_date.keys())))

mismatches = []
for date in all_dates:
    csv_count = len(csv_by_date[date])
    db_count = len(db_by_date[date])
    
    if csv_count != db_count:
        diff = csv_count - db_count
        status = "CSV has more" if diff > 0 else "DB has more"
        mismatches.append((date, csv_count, db_count, diff, status))
        print(f"{date} | CSV: {csv_count:2d} | DB: {db_count:2d} | Diff: {diff:+3d} | {status}")

print(f"\n{'=' * 80}")
print(f"TOTALS: CSV: {len(csv_transactions)} transactions, DB: {len(db_transactions)} transactions, Difference: {len(csv_transactions) - len(db_transactions)}")
print(f"{'=' * 80}")

if mismatches:
    print(f"\n⚠️  {len(mismatches)} dates with mismatches")
else:
    print("\n✓ All dates match perfectly!")

cur.close()
conn.close()
