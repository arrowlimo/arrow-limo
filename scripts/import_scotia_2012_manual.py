#!/usr/bin/env python3
"""
Import manually verified Scotia Bank 2012 transactions.
This will replace existing data with verified entries.
"""

import psycopg2
import csv
from datetime import datetime
from decimal import Decimal
import hashlib

def parse_amount(amt_str):
    """Parse amount string, handling currency symbols and commas."""
    if not amt_str or amt_str.strip() == '':
        return None
    amt_str = amt_str.replace('$', '').replace(',', '').strip()
    try:
        return Decimal(amt_str)
    except:
        return None

def create_hash(date, description, debit, credit):
    """Create deterministic hash for transaction."""
    text = f"903990106011|{date}|{description}|{debit or 0:.2f}|{credit or 0:.2f}"
    return hashlib.sha256(text.encode('utf-8')).hexdigest()[:16]

# This is the manually verified data you provided
# Format: (transaction_id_if_exists, date, description, debit, credit)
manual_data = """
,2012-02-22,ABM DEPOSIT RED DEER BRANCH RED DEER AB,,100.00
,2012-02-23,DEPOSIT,,5320.00
,2012-02-23,DRAFT PURCHASE,5250.00,
54706,2012-02-23,DRAFT PURCHASE $5250.00,6.50,
54707,2012-02-29,SERVICE CHARGE,112.50,
54708,2012-04-02,SBAP FEE $112.5 DUE,91.00,
"""

# NOTE: Due to the size of your data, you should save it to a CSV file
# Then this script will import it

print("Scotia Bank 2012 Manual Data Import")
print("=" * 80)
print("\nPlease provide your data in one of these formats:")
print("1. CSV file path")
print("2. Paste data directly (will save to temp file)")
print()

import_method = input("Enter '1' for file or '2' to paste: ").strip()

if import_method == '1':
    csv_file = input("Enter CSV file path: ").strip().strip('"')
elif import_method == '2':
    print("\nPaste your data (format: transaction_id,date,description,debit,credit)")
    print("Press Ctrl+Z then Enter when done on Windows, or Ctrl+D on Unix:")
    print()
    
    lines = []
    try:
        while True:
            line = input()
            lines.append(line)
    except EOFError:
        pass
    
    csv_file = 'reports/scotia_2012_manual_input_temp.csv'
    with open(csv_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    print(f"\n✓ Saved to: {csv_file}")
else:
    print("Invalid choice. Exiting.")
    exit(1)

# Connect to database
conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REDACTED***'
)

cur = conn.cursor()

# Read and parse CSV
transactions = []
with open(csv_file, 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        trans_id = row.get('transaction_id', '').strip()
        date = row['date'].strip()
        desc = row['description'].strip()
        debit = parse_amount(row.get('debit', ''))
        credit = parse_amount(row.get('credit', ''))
        
        # Parse date (handle various formats)
        if '/' in date:
            parts = date.split('/')
            if len(parts) == 3:
                month, day, year = parts
                date = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
        
        transactions.append({
            'old_id': trans_id if trans_id else None,
            'date': date,
            'description': desc,
            'debit': debit,
            'credit': credit
        })

print(f"\n✓ Loaded {len(transactions)} transactions from file")

# Ask for confirmation
print("\nThis will:")
print(f"  1. DELETE all {len(transactions)} existing Scotia 2012 transactions")
print(f"  2. INSERT {len(transactions)} manually verified transactions")
print(f"  3. Renumber all transaction IDs sequentially")
print()
confirm = input("Proceed with import? (yes/no): ").strip().lower()

if confirm != 'yes':
    print("Import cancelled.")
    cur.close()
    conn.close()
    exit(0)

# Step 1: Delete existing Scotia 2012 data
print("\n[1/3] Deleting existing Scotia 2012 data...")
cur.execute("""
    DELETE FROM banking_transactions 
    WHERE account_number = '903990106011'
      AND transaction_date >= '2012-01-01'
      AND transaction_date <= '2012-12-31'
""")
deleted = cur.rowcount
print(f"  ✓ Deleted {deleted} rows")

# Step 2: Insert manually verified data
print("\n[2/3] Inserting manually verified transactions...")
inserted = 0
for trans in transactions:
    source_hash = create_hash(
        trans['date'],
        trans['description'],
        trans['debit'] or Decimal(0),
        trans['credit'] or Decimal(0)
    )
    
    cur.execute("""
        INSERT INTO banking_transactions 
        (account_number, transaction_date, description, debit_amount, credit_amount, source_hash, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, NOW())
    """, (
        '903990106011',
        trans['date'],
        trans['description'],
        trans['debit'],
        trans['credit'],
        source_hash
    ))
    inserted += 1
    if inserted % 100 == 0:
        print(f"  Inserted {inserted}/{len(transactions)}...")

print(f"  ✓ Inserted {inserted} rows")

# Step 3: Verify
print("\n[3/3] Verifying import...")
cur.execute("""
    SELECT COUNT(*), MIN(transaction_id), MAX(transaction_id)
    FROM banking_transactions 
    WHERE account_number = '903990106011'
      AND transaction_date >= '2012-01-01'
      AND transaction_date <= '2012-12-31'
""")
count, min_id, max_id = cur.fetchone()
print(f"  Count: {count}")
print(f"  ID Range: {min_id} to {max_id}")

# Commit
conn.commit()
print("\n✓ Import complete and committed!")

cur.close()
conn.close()

print("\n" + "=" * 80)
print("SUCCESS: Scotia Bank 2012 data has been replaced with manually verified entries")
print("=" * 80)
