#!/usr/bin/env python3
"""Import CIBC checking account 0228362 for Nov-Dec 2025."""
import psycopg2
import csv
from datetime import datetime
import hashlib

conn = psycopg2.connect(dbname='almsdata', user='postgres', password='***REDACTED***', host='localhost')
cur = conn.cursor()

print("=" * 100)
print("IMPORTING CIBC CHECKING ACCOUNT 0228362 - NOV/DEC 2025")
print("=" * 100)
print()

csv_file = r"L:\limo\CIBC UPLOADS\0228362 (CIBC checking account)\2025cibc (1).csv"

# Read and parse
transactions = []
with open(csv_file, 'r', encoding='utf-8-sig') as f:
    reader = csv.reader(f)
    for row in reader:
        if len(row) < 3:
            continue
        
        try:
            # MM/DD/YYYY format
            tx_date = datetime.strptime(row[0].strip(), '%m/%d/%Y').date()
        except:
            continue
            
        description = row[1].strip()
        debit_str = row[2].strip()
        credit_str = row[3].strip() if len(row) > 3 else ""
        
        debit_amt = float(debit_str) if debit_str else None
        credit_amt = float(credit_str) if credit_str else None
        
        # Create unique hash
        hash_input = f"0228362|{tx_date}|{description}|{debit_amt}|{credit_amt}"
        tx_hash = hashlib.sha256(hash_input.encode()).hexdigest()
        
        transactions.append({
            'date': tx_date,
            'description': description,
            'debit': debit_amt,
            'credit': credit_amt,
            'hash': tx_hash
        })

print(f"Parsed {len(transactions)} transactions from CSV")
if transactions:
    print(f"Date range: {min(t['date'] for t in transactions)} to {max(t['date'] for t in transactions)}")
print()

# Filter to Nov-Dec 2025 only
nov_dec_2025 = [t for t in transactions if t['date'].year == 2025 and t['date'].month >= 11]
print(f"Filtered to Nov-Dec 2025: {len(nov_dec_2025)} transactions")
print()

# Check existing
cur.execute("""
    SELECT COUNT(*) 
    FROM banking_transactions 
    WHERE account_number LIKE '%0228362%'
    AND transaction_date >= '2025-11-01'
    AND transaction_date < '2026-01-01'
""")
existing_count = cur.fetchone()[0]
print(f"Existing Nov-Dec 2025 transactions in DB: {existing_count}")

if existing_count > 0:
    print("\n⚠️ WARNING: Nov-Dec 2025 data already exists. Deduplication will be applied.")

# Insert with deduplication
inserted = 0
skipped = 0

for tx in nov_dec_2025:
    # Check if hash exists
    cur.execute("SELECT COUNT(*) FROM banking_transactions WHERE transaction_hash = %s", (tx['hash'],))
    if cur.fetchone()[0] > 0:
        skipped += 1
        continue
    
    # Insert
    cur.execute("""
        INSERT INTO banking_transactions (
            account_number, transaction_date, description,
            debit_amount, credit_amount, transaction_hash
        ) VALUES (%s, %s, %s, %s, %s, %s)
    """, (
        '0228362',
        tx['date'],
        tx['description'],
        tx['debit'],
        tx['credit'],
        tx['hash']
    ))
    inserted += 1

conn.commit()

print("\n" + "=" * 100)
print("IMPORT COMPLETE")
print("=" * 100)
print(f"✓ Inserted: {inserted} new transactions")
print(f"⊘ Skipped (duplicates): {skipped}")
print(f"Total processed: {len(nov_dec_2025)}")

# Summary by month
print("\n" + "=" * 100)
print("MONTHLY SUMMARY (ACCOUNT 0228362)")
print("=" * 100)

cur.execute("""
    SELECT 
        TO_CHAR(transaction_date, 'YYYY-MM') as month,
        COUNT(*) as count,
        SUM(debit_amount) as debits,
        SUM(credit_amount) as credits
    FROM banking_transactions
    WHERE account_number LIKE '%0228362%'
    AND transaction_date >= '2025-11-01'
    AND transaction_date < '2026-01-01'
    GROUP BY TO_CHAR(transaction_date, 'YYYY-MM')
    ORDER BY month
""")

print(f"{'Month':10} | {'Count':>6} | {'Debits':>15} | {'Credits':>15}")
print("-" * 60)
for month, count, debits, credits in cur.fetchall():
    debits = debits or 0.0
    credits = credits or 0.0
    print(f"{month:10} | {count:6,} | ${debits:>14,.2f} | ${credits:>14,.2f}")

conn.close()
