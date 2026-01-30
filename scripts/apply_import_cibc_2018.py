#!/usr/bin/env python3
"""
Import missing HEFFNER AUTO transactions from CIBC 2018 CSV.
These are legitimate duplicate weekly payments identified in the bank statement.
"""
import csv
import psycopg2
from datetime import datetime
import hashlib
import sys

csv_file = r"L:\limo\CIBC UPLOADS\0228362 (CIBC checking account)\cibc 8362 2018.csv"

# Parse CSV - match by date + amount only
csv_by_date_amt = {}
with open(csv_file, 'r', encoding='utf-8') as f:
    reader = csv.reader(f)
    for row in reader:
        if len(row) >= 3:
            date_str = row[0]
            desc = row[1]
            debit = row[2].strip() if row[2].strip() else None
            credit = row[3].strip() if row[3].strip() else None
            
            try:
                date = datetime.strptime(date_str, '%Y-%m-%d').date()
                debit_amt = float(debit) if debit else None
                credit_amt = float(credit) if credit else None
                amount = debit_amt if debit_amt else credit_amt
                
                key = f"{date}|{amount:.2f}"
                
                if key not in csv_by_date_amt:
                    csv_by_date_amt[key] = []
                csv_by_date_amt[key].append({
                    'date': date, 
                    'desc': desc, 
                    'debit': debit_amt,
                    'credit': credit_amt,
                    'amount': amount
                })
            except ValueError:
                pass

# Get from DB
conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()

cur.execute("""
    SELECT 
        transaction_date,
        description,
        debit_amount,
        credit_amount
    FROM banking_transactions
    WHERE account_number = '0228362'
        AND EXTRACT(YEAR FROM transaction_date) = 2018
""")

db_by_date_amt = {}
for date, desc, debit, credit in cur.fetchall():
    debit_amt = float(debit) if debit else None
    credit_amt = float(credit) if credit else None
    amount = debit_amt if debit_amt else credit_amt
    
    key = f"{date}|{amount:.2f}"
    if key not in db_by_date_amt:
        db_by_date_amt[key] = []
    db_by_date_amt[key].append({
        'date': date,
        'desc': desc,
        'debit': debit_amt,
        'credit': credit_amt,
        'amount': amount
    })

# Find missing in DB
missing = []
for key in csv_by_date_amt:
    if key not in db_by_date_amt:
        for txn in csv_by_date_amt[key]:
            missing.append((key, txn))
    elif len(csv_by_date_amt[key]) > len(db_by_date_amt.get(key, [])):
        db_count = len(db_by_date_amt[key])
        for i, txn in enumerate(csv_by_date_amt[key]):
            if i >= db_count:
                missing.append((key, txn))

print(f"Found {len(missing)} transactions to import\n")

if not missing:
    print("No missing transactions found. Database is in sync with CSV.")
    sys.exit(0)

# Import missing transactions
imported_count = 0
for key, txn in sorted(missing):
    debit = txn['debit'] if txn['debit'] else None
    credit = txn['credit'] if txn['credit'] else None
    
    # Create source hash
    source_data = f"{txn['date']}|{txn['desc']}|{debit}|{credit}"
    source_hash = hashlib.sha256(source_data.encode()).hexdigest()
    
    # Escape single quotes in description
    desc_escaped = txn['desc'].replace("'", "''")
    
    cur.execute("""
        INSERT INTO banking_transactions (
            account_number, transaction_date, posted_date,
            description, debit_amount, credit_amount,
            bank_id, source_file, import_batch,
            source_hash, reconciliation_status, created_at
        ) VALUES (
            %s, %s, %s,
            %s, %s, %s,
            1, %s, %s,
            %s, %s, NOW()
        )
    """, (
        '0228362',
        txn['date'],
        txn['date'],
        txn['desc'],
        debit,
        credit,
        'cibc 8362 2018.csv',
        'CIBC_2018_IMPORT',
        source_hash,
        'unreconciled'
    ))
    imported_count += 1
    print(f"✓ {txn['date']} | ${txn['amount']:.2f} | {txn['desc'][:50]}")

# Commit
conn.commit()
cur.close()
conn.close()

print()
print("=" * 75)
print(f"✅ Successfully imported {imported_count} transactions")
print("=" * 75)
