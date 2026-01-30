#!/usr/bin/env python3
"""Import Scotia Bank 2012 manually verified data."""

import psycopg2
import csv
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

csv_file = r'L:\limo\CIBC UPLOADS\scotiabank verified data.csv'

print("=" * 80)
print("SCOTIA BANK 2012 MANUAL DATA IMPORT")
print("=" * 80)
print(f"\nFile: {csv_file}")

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
        trans_id = row.get('Transaction ID', '').strip()
        date_str = row.get('Date', '').strip()
        desc = row.get('Description', '').strip()
        debit = parse_amount(row.get('Debit', ''))
        credit = parse_amount(row.get('Credit', ''))
        
        # Parse date
        if date_str:
            # Handle MM/DD/YYYY format
            if '/' in date_str:
                parts = date_str.split('/')
                if len(parts) == 3:
                    month, day, year = parts
                    date_str = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
        
        transactions.append({
            'old_id': trans_id if trans_id else None,
            'date': date_str,
            'description': desc,
            'debit': debit,
            'credit': credit
        })

print(f"✓ Loaded {len(transactions)} transactions")

# Delete existing Scotia 2012 data
print("\nDeleting existing Scotia 2012 data...")

# First, remove any foreign key references in banking_payment_links
print("  Removing payment links...")
cur.execute("""
    DELETE FROM banking_payment_links
    WHERE banking_transaction_id IN (
        SELECT transaction_id FROM banking_transactions
        WHERE account_number = '903990106011'
          AND transaction_date >= '2012-01-01'
          AND transaction_date <= '2012-12-31'
    )
""")
payment_links_deleted = cur.rowcount
print(f"  Deleted {payment_links_deleted} payment link(s)")

# Now safe to delete the transactions
print("  Deleting transactions...")
cur.execute("""
    DELETE FROM banking_transactions 
    WHERE account_number = '903990106011'
      AND transaction_date >= '2012-01-01'
      AND transaction_date <= '2012-12-31'
""")
deleted = cur.rowcount
print(f"✓ Deleted {deleted} rows")

# Insert manually verified data
print("\nInserting manually verified transactions...")
inserted = 0
for trans in transactions:
    if not trans['date']:
        continue
        
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
        print(f"  {inserted}/{len(transactions)}...")

print(f"✓ Inserted {inserted} rows")

# Verify
cur.execute("""
    SELECT COUNT(*), MIN(transaction_id), MAX(transaction_id)
    FROM banking_transactions 
    WHERE account_number = '903990106011'
      AND transaction_date >= '2012-01-01'
      AND transaction_date <= '2012-12-31'
""")
count, min_id, max_id = cur.fetchone()
print(f"\nVerification:")
print(f"  Count: {count}")
print(f"  ID Range: {min_id} to {max_id}")

# Commit
conn.commit()
print("\n✓ Import complete!")

cur.close()
conn.close()
