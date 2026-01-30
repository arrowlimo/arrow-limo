#!/usr/bin/env python3
"""Import Scotia Bank 2012 normalized transactions (2,677 records)."""

import psycopg2
import csv
from decimal import Decimal
import hashlib
import sys

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
    text = f"3714081|{date}|{description}|{debit or 0:.2f}|{credit or 0:.2f}"
    return hashlib.sha256(text.encode('utf-8')).hexdigest()

csv_file = r'l:\limo\staging\2012_comparison\scotia_statement_transactions_2012_normalized.csv'

print("=" * 80)
print("SCOTIA BANK 2012 NORMALIZED DATA IMPORT")
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

# Check existing Scotia 2012 data
cur.execute("""
    SELECT COUNT(*), 
           COALESCE(SUM(debit_amount), 0) as total_debits,
           COALESCE(SUM(credit_amount), 0) as total_credits
    FROM banking_transactions
    WHERE account_number = '3714081'
      AND EXTRACT(YEAR FROM transaction_date) = 2012
""")
existing = cur.fetchone()
print(f"\nExisting Scotia 2012 records: {existing[0]} (debits: ${existing[1]:,.2f}, credits: ${existing[2]:,.2f})")

# Read and parse CSV
transactions = []
total_debits = Decimal('0')
total_credits = Decimal('0')

with open(csv_file, 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        date_str = row.get('transaction_date', '').strip()
        desc = row.get('description', '').strip()
        debit_str = row.get('debit_amount', '').strip()
        credit_str = row.get('credit_amount', '').strip()
        source_ref = row.get('source_reference', '').strip()
        
        debit = parse_amount(debit_str) if debit_str else None
        credit = parse_amount(credit_str) if credit_str else None
        
        if debit:
            total_debits += debit
        if credit:
            total_credits += credit
        
        trans_hash = create_hash(date_str, desc, debit, credit)
        
        transactions.append({
            'date': date_str,
            'description': desc,
            'debit': debit,
            'credit': credit,
            'source_hash': trans_hash,
            'source_reference': source_ref
        })

print(f"✓ Loaded {len(transactions)} transactions from CSV")
print(f"  Total debits:  ${total_debits:,.2f}")
print(f"  Total credits: ${total_credits:,.2f}")
print(f"  Net flow:      ${total_credits - total_debits:,.2f}")

# Check for duplicates in CSV against existing DB records
print("\nChecking for duplicates...")
hashes = [t['source_hash'] for t in transactions]
placeholders = ','.join(['%s'] * len(hashes))
cur.execute(f"""
    SELECT source_hash, COUNT(*) 
    FROM banking_transactions
    WHERE source_hash IN ({placeholders})
      AND account_number = '3714081'
    GROUP BY source_hash
""", hashes)
existing_hashes = {row[0]: row[1] for row in cur.fetchall()}
duplicate_count = sum(1 for t in transactions if t['source_hash'] in existing_hashes)

print(f"  Duplicate transactions (already in DB): {duplicate_count}")
print(f"  New transactions to import: {len(transactions) - duplicate_count}")

# Confirm import
if duplicate_count < len(transactions):
    response = input("\nProceed with import? (yes/no): ").strip().lower()
    if response != 'yes':
        print("Import cancelled.")
        sys.exit(0)

# Import transactions (skip duplicates)
imported = 0
skipped = 0

for t in transactions:
    if t['source_hash'] in existing_hashes:
        skipped += 1
        continue
    
    try:
        cur.execute("""
            INSERT INTO banking_transactions (
                account_number, 
                transaction_date, 
                description,
                debit_amount,
                credit_amount,
                source_hash,
                notes
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (
            '3714081',
            t['date'],
            t['description'][:500],  # Truncate long descriptions
            t['debit'],
            t['credit'],
            t['source_hash'],
            f"Imported from {t['source_reference']}" if t['source_reference'] else None
        ))
        imported += 1
    except Exception as e:
        print(f"  ERROR on {t['date']} {t['description'][:50]}: {e}")
        conn.rollback()
        continue

conn.commit()

print(f"\n{'=' * 80}")
print(f"IMPORT COMPLETE")
print(f"{'=' * 80}")
print(f"  Imported: {imported}")
print(f"  Skipped (duplicates): {skipped}")

# Verify final counts
cur.execute("""
    SELECT COUNT(*), 
           COALESCE(SUM(debit_amount), 0) as total_debits,
           COALESCE(SUM(credit_amount), 0) as total_credits
    FROM banking_transactions
    WHERE account_number = '3714081'
      AND EXTRACT(YEAR FROM transaction_date) = 2012
""")
final = cur.fetchone()
print(f"\nFinal Scotia 2012 records: {final[0]} (debits: ${final[1]:,.2f}, credits: ${final[2]:,.2f})")

cur.close()
conn.close()
