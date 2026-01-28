#!/usr/bin/env python3
"""
Match CIBC 2018 CSV transactions against database banking_transactions.
CIBC account: 0228362 (mapped_bank_account_id = 1)
"""
import csv
import psycopg2
from datetime import datetime
from collections import defaultdict

DB_HOST = "localhost"
DB_NAME = "almsdata"
DB_USER = "postgres"
DB_PASSWORD = os.environ.get("DB_PASSWORD")

# Parse CSV
csv_file = r"L:\limo\CIBC UPLOADS\0228362 (CIBC checking account)\cibc 8362 2018.csv"
csv_txns = []

with open(csv_file, 'r', encoding='utf-8') as f:
    reader = csv.reader(f)
    for row in reader:
        if len(row) >= 3:
            date_str = row[0]
            description = row[1]
            # Column 2 = debit (out), Column 3 = credit (in)
            debit = row[2].strip() if row[2].strip() else None
            credit = row[3].strip() if row[3].strip() else None
            
            try:
                date = datetime.strptime(date_str, '%Y-%m-%d').date()
                debit_amt = float(debit) if debit else None
                credit_amt = float(credit) if credit else None
                csv_txns.append({
                    'date': date,
                    'description': description,
                    'debit': debit_amt,
                    'credit': credit_amt,
                    'amount': debit_amt if debit_amt else credit_amt,
                    'is_debit': bool(debit_amt)
                })
            except ValueError as e:
                print(f"Skipped row: {row} - {e}")

print(f"CSV contains {len(csv_txns)} transactions")

# Query database
conn = psycopg2.connect(
    host=DB_HOST,
    database=DB_NAME,
    user=DB_USER,
    password=DB_PASSWORD
)
cur = conn.cursor()

# Get all 2018 CIBC transactions from DB (CIBC 0228362)
cur.execute("""
    SELECT 
        transaction_date,
        COALESCE(vendor_extracted, description) as description,
        CASE 
            WHEN debit_amount IS NOT NULL AND debit_amount > 0 THEN -debit_amount
            WHEN credit_amount IS NOT NULL AND credit_amount > 0 THEN credit_amount
            ELSE 0
        END as amount
    FROM banking_transactions
    WHERE account_number = '0228362'
        AND EXTRACT(YEAR FROM transaction_date) = 2018
    ORDER BY transaction_date DESC
""")

db_txns = cur.fetchall()
cur.close()
conn.close()

print(f"Database contains {len(db_txns)} transactions for CIBC 2018")
print()

# Build lookup dictionaries by date+amount using absolute values
csv_by_date_amt = defaultdict(list)
for i, txn in enumerate(csv_txns):
    key = (txn['date'], abs(txn['amount']))  # Store absolute values
    csv_by_date_amt[key].append((i, txn))

db_by_date_amt = defaultdict(list)
for i, (date, desc, amt) in enumerate(db_txns):
    key = (date, abs(amt))  # Database already gives signed amounts
    db_by_date_amt[key].append((i, (date, desc, amt)))

# Find matches
matched_csv = set()
matched_db = set()
mismatches = []

for (date, amount), csv_list in csv_by_date_amt.items():
    key = (date, amount)
    if key in db_by_date_amt:
        db_list = db_by_date_amt[key]
        # Match 1:1 by count
        for csv_idx, csv_txn in enumerate(csv_list):
            if csv_idx < len(db_list):
                db_idx, db_txn = db_list[csv_idx]
                matched_csv.add(id(csv_txn))
                matched_db.add(id(db_txn))

# Report missing in database
print("=" * 80)
print("TRANSACTIONS IN CSV BUT NOT IN DATABASE (by date, descending)")
print("=" * 80)

missing = [t for t in csv_txns if id(t) not in matched_csv]
missing_by_date = sorted(missing, key=lambda x: x['date'], reverse=True)

print(f"\nFound {len(missing)} missing transactions:\n")
for txn in missing_by_date[:50]:  # Show first 50
    amt_str = f"${txn['amount']:.2f}" if txn['amount'] else "N/A"
    txn_type = "OUT" if txn['is_debit'] else "IN"
    print(f"{txn['date']} | {txn_type:3} | {amt_str:>10} | {txn['description'][:60]}")

if len(missing) > 50:
    print(f"\n... and {len(missing) - 50} more missing transactions")

# Report extra in database
print("\n" + "=" * 80)
print("TRANSACTIONS IN DATABASE BUT NOT IN CSV (by date, descending)")
print("=" * 80)

extra = [t for t in db_txns if id(t) not in matched_db]
extra_by_date = sorted(extra, key=lambda x: x[0], reverse=True)

print(f"\nFound {len(extra)} extra transactions:\n")
for date, desc, amt in extra_by_date[:50]:
    amt_str = f"${abs(amt):.2f}"
    txn_type = "DEBIT" if amt < 0 else "CREDIT"
    print(f"{date} | {txn_type:6} | {amt_str:>10} | {desc[:60]}")

if len(extra) > 50:
    print(f"\n... and {len(extra) - 50} more extra transactions")

# Summary
print("\n" + "=" * 80)
print("SUMMARY")
print("=" * 80)
print(f"CSV transactions:               {len(csv_txns)}")
print(f"Database transactions:          {len(db_txns)}")
print(f"Matched (date+amount):          {len([t for t in csv_txns if id(t) in matched_csv])}")
print(f"Missing in database:            {len(missing)}")
print(f"Extra in database:              {len(extra)}")
print(f"Balance difference:             {len(missing) - len(extra)}")
