#!/usr/bin/env python3
"""
Import missing CIBC 2018 transactions from CSV into database.
The bank CSV is the source of truth.
"""
import csv
import psycopg2
from datetime import datetime
import hashlib

csv_file = r"L:\limo\CIBC UPLOADS\0228362 (CIBC checking account)\cibc 8362 2018.csv"

# Parse CSV - match by date + amount only (descriptions may be cleaned in DB)
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
                
                # Key: date + amount (ignore description, may be cleaned in DB)
                key = f"{date}|{amount:.2f}"
                
                # Store all transactions for this date+amount (in case of duplicates)
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

# Get from DB - match by date + amount
conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
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
    
    # Key: date + amount
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

# Find missing in DB - use date+amount matching
missing = []
for key in csv_by_date_amt:
    if key not in db_by_date_amt:
        # All transactions at this date+amount in CSV are missing
        for txn in csv_by_date_amt[key]:
            missing.append((key, txn))
    elif len(csv_by_date_amt[key]) > len(db_by_date_amt.get(key, [])):
        # CSV has more transactions at this date+amount than DB (likely duplicates)
        db_count = len(db_by_date_amt[key])
        for i, txn in enumerate(csv_by_date_amt[key]):
            if i >= db_count:
                missing.append((key, txn))

print(f"Found {len(missing)} transactions in CSV but not in database")
print()

if missing:
    print("MISSING TRANSACTIONS TO IMPORT:")
    print(f"{'Date':<12} {'Amount':>12} {'Description':<50}")
    print("-" * 75)
    
    for key, txn in sorted(missing, reverse=True):
        amt = txn['debit'] if txn['debit'] else txn['credit']
        print(f"{txn['date']} | ${amt:>11.2f} | {txn['desc'][:48]}")
    
    print()
    print("=" * 75)
    print("DRY RUN MODE - Use --write to import")
    print("=" * 75)
    print()
    
    # Show the SQL that would be executed
    print("SQL to be executed:")
    print()
    
    for key, txn in sorted(missing):
        debit = f"{txn['debit']:.2f}" if txn['debit'] else "NULL"
        credit = f"{txn['credit']:.2f}" if txn['credit'] else "NULL"
        
        # Create a source hash from the data
        source_data = f"{txn['date']}|{txn['desc']}|{debit}|{credit}"
        source_hash = hashlib.sha256(source_data.encode()).hexdigest()
        
        print(f"""
INSERT INTO banking_transactions (
    account_number, transaction_date, posted_date,
    description, debit_amount, credit_amount,
    bank_id, source_file, import_batch,
    source_hash, reconciliation_status, created_at
) VALUES (
    '0228362', '{txn['date']}', '{txn['date']}',
    E'{txn['desc'].replace("'", "''")}', 
    {debit if txn['debit'] else 'NULL'}, 
    {credit if txn['credit'] else 'NULL'},
    1, 'cibc 8362 2018.csv', 'CIBC_2018_IMPORT',
    '{source_hash}', 'unreconciled', NOW()
);""")

cur.close()
conn.close()
