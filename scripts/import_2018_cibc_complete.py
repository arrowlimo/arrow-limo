#!/usr/bin/env python3
"""Import 2018 CIBC transactions, mark NSF matches, create receipts with GL categories."""

import pandas as pd
import psycopg2
from psycopg2.extras import execute_values
import hashlib
from datetime import datetime

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REDACTED***'
)
cur = conn.cursor()

# Read the Excel file
df = pd.read_excel(r'L:\limo\CIBC UPLOADS\0228362 (CIBC checking account)\2018 CIBC 8362.xlsx')

print(f"Total transactions in Excel: {len(df)}")
print(f"Date range: {df['date'].min()} to {df['date'].max()}\n")

# Check what's already in database
cur.execute("""
    SELECT MIN(transaction_date), MAX(transaction_date), COUNT(*)
    FROM banking_transactions
    WHERE account_number LIKE '%8362'
    AND EXTRACT(YEAR FROM transaction_date) = 2018
""")
db_min, db_max, db_count = cur.fetchone()
print(f"Database has: {db_count} transactions from {db_min} to {db_max}\n")

# Filter to only new transactions (before Sept 13, 2018)
new_df = df[df['date'] < '2018-09-13'].copy()
print(f"Transactions to import (before 2018-09-13): {len(new_df)}\n")

# Prepare import data
import_data = []
account_number = '0228362'

for idx, row in new_df.iterrows():
    description = str(row['Description'])
    trans_date = row['date']
    
    # Determine debit/credit amounts
    debit = row['debit/withdrawal'] if pd.notna(row['debit/withdrawal']) else None
    credit = row['deposit/credit'] if pd.notna(row['deposit/credit']) else None
    balance = row['balance'] if pd.notna(row['balance']) else None
    
    # Create unique hash for deduplication
    hash_string = f"{account_number}|{trans_date}|{description}|{debit}|{credit}|{idx}"
    transaction_hash = hashlib.sha256(hash_string.encode()).hexdigest()
    
    # Extract vendor
    vendor = description[:50] if description else None
    
    import_data.append((
        account_number,
        trans_date,
        trans_date,  # posted_date same as transaction_date
        description,
        debit,
        credit,
        balance,
        vendor,
        '2018 CIBC 8362.xlsx',
        'import_2018_cibc_complete',
        1,  # bank_id for CIBC
        transaction_hash
    ))

print(f"Prepared {len(import_data)} transactions for import\n")

# Insert transactions with deduplication check
if len(import_data) > 0:
    inserted = 0
    for data in import_data:
        # Check if already exists
        cur.execute("""
            SELECT COUNT(*) FROM banking_transactions
            WHERE account_number = %s 
            AND transaction_date = %s
            AND description = %s
            AND COALESCE(debit_amount, 0) = COALESCE(%s, 0)
            AND COALESCE(credit_amount, 0) = COALESCE(%s, 0)
        """, (data[0], data[1], data[3], data[4], data[5]))
        
        if cur.fetchone()[0] == 0:
            # Insert
            cur.execute("""
                INSERT INTO banking_transactions (
                    account_number, transaction_date, posted_date, description,
                    debit_amount, credit_amount, balance, vendor_extracted,
                    source_file, import_batch, bank_id, transaction_hash
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, data)
            inserted += 1
    
    conn.commit()
    print(f"✅ Imported {inserted} new transactions\n")

# Now mark NSF matches
print("=" * 80)
print("MARKING NSF MATCHES")
print("=" * 80)

cur.execute("""
    SELECT transaction_id, transaction_date, description, 
           COALESCE(debit_amount, 0) as debit,
           COALESCE(credit_amount, 0) as credit
    FROM banking_transactions
    WHERE account_number LIKE '%8362'
    AND EXTRACT(YEAR FROM transaction_date) = 2018
    AND (description ILIKE '%NSF%' OR description ILIKE '%RETURN%')
    ORDER BY transaction_date, transaction_id
""")

nsf_transactions = cur.fetchall()
print(f"Found {len(nsf_transactions)} potential NSF transactions\n")

# Group by date and amount to find pairs
nsf_pairs = []
for i, trans in enumerate(nsf_transactions):
    tid1, date1, desc1, debit1, credit1 = trans
    
    # Look for matching reversal
    for j, other in enumerate(nsf_transactions[i+1:], start=i+1):
        tid2, date2, desc2, debit2, credit2 = other
        
        # Check if same date and amounts match (debit matches credit)
        if date1 == date2:
            if abs(debit1 - credit2) < 0.01 or abs(credit1 - debit2) < 0.01:
                # Found a pair
                nsf_pairs.append((tid1, tid2, date1, desc1, desc2, max(debit1, credit1, debit2, credit2)))
                print(f"NSF Pair: {date1} | {desc1[:40]:40s} | {desc2[:40]:40s} | ${max(debit1, credit1, debit2, credit2):,.2f}")

print(f"\nFound {len(nsf_pairs)} NSF pairs")

# Mark NSF charges
for tid1, tid2, date, desc1, desc2, amount in nsf_pairs:
    cur.execute("""
        UPDATE banking_transactions
        SET is_nsf_charge = TRUE,
            reconciliation_notes = 'NSF pair auto-detected'
        WHERE transaction_id IN (%s, %s)
    """, (tid1, tid2))

conn.commit()
print(f"✅ Marked {len(nsf_pairs) * 2} transactions as NSF pairs\n")

# Get GL category mappings from historical data
print("=" * 80)
print("CREATING RECEIPTS WITH GL CATEGORIES")
print("=" * 80)

# Build vendor -> expense account mapping from existing receipts
cur.execute("""
    SELECT DISTINCT vendor_name, expense_account
    FROM receipts
    WHERE vendor_name IS NOT NULL 
    AND expense_account IS NOT NULL
    AND vendor_name != ''
""")

vendor_account_map = {}
for vendor, acct in cur.fetchall():
    vendor_clean = vendor.strip().upper()
    if vendor_clean not in vendor_account_map and acct:
        vendor_account_map[vendor_clean] = acct

print(f"Loaded {len(vendor_account_map)} vendor -> account mappings\n")

# Get all 2018 transactions that don't have receipts
cur.execute("""
    SELECT bt.transaction_id, bt.transaction_date, bt.description,
           bt.debit_amount, bt.credit_amount, bt.vendor_extracted,
           bt.is_nsf_charge
    FROM banking_transactions bt
    WHERE bt.account_number LIKE '%8362'
    AND EXTRACT(YEAR FROM bt.transaction_date) = 2018
    AND NOT EXISTS (
        SELECT 1 FROM receipts r 
        WHERE r.banking_transaction_id = bt.transaction_id
    )
    AND bt.is_nsf_charge IS NOT TRUE
    ORDER BY bt.transaction_date
""")

transactions_need_receipts = cur.fetchall()
print(f"Transactions needing receipts: {len(transactions_need_receipts)}\n")

# Create receipts
receipts_created = 0
for trans_id, trans_date, description, debit, credit, vendor, is_nsf in transactions_need_receipts:
    
    # Determine amount and type
    if debit and debit > 0:
        amount = debit
        receipt_type = 'expense'
    elif credit and credit > 0:
        amount = credit
        receipt_type = 'income'
    else:
        continue
    
    # Try to match expense account
    vendor_clean = (vendor or description or '').strip().upper()[:50]
    expense_account = None
    category = None
    
    # Try exact match first
    if vendor_clean in vendor_account_map:
        expense_account = vendor_account_map[vendor_clean]
    else:
        # Try partial match
        for known_vendor, acct in vendor_account_map.items():
            if known_vendor in vendor_clean or vendor_clean in known_vendor:
                expense_account = acct
                break
    
    # Default categories if no match
    if not expense_account:
        if 'SQUARE' in vendor_clean:
            category = 'Revenue'
            expense_account = '4000'
        elif 'FAS GAS' in vendor_clean or 'HUSKY' in vendor_clean or 'ESSO' in vendor_clean:
            category = 'Fuel'
            expense_account = '5200'
        elif 'BANK' in vendor_clean and 'FEE' in vendor_clean:
            category = 'Bank Fees'
            expense_account = '5400'
        elif 'NSF' in vendor_clean:
            category = 'Bank Fees'
            expense_account = '5400'
        elif 'INSURANCE' in vendor_clean:
            category = 'Insurance'
            expense_account = '5600'
        elif 'HEFFNER' in vendor_clean:
            category = 'Vehicle Lease/Finance'
            expense_account = '5700'
        elif 'LIQUOR' in vendor_clean or 'SOBEYS' in vendor_clean or 'SUPERSTORE' in vendor_clean:
            category = 'Supplies'
            expense_account = '5100'
        else:
            category = 'Uncategorized'
            expense_account = None
    
    # Insert receipt
    cur.execute("""
        INSERT INTO receipts (
            receipt_date, vendor_name, gross_amount, type,
            banking_transaction_id, created_from_banking,
            expense_account, category, comment
        ) VALUES (%s, %s, %s, %s, %s, TRUE, %s, %s, %s)
    """, (
        trans_date,
        vendor_clean[:100] if vendor_clean else 'Unknown',
        amount,
        receipt_type,
        trans_id,
        expense_account,
        category,
        f'Auto-created from 2018 CIBC: {description[:100]}'
    ))
    
    receipts_created += 1

conn.commit()
print(f"✅ Created {receipts_created} receipts\n")

# Summary
print("=" * 80)
print("SUMMARY")
print("=" * 80)

cur.execute("""
    SELECT COUNT(*), 
           SUM(CASE WHEN debit_amount IS NOT NULL THEN debit_amount ELSE 0 END) as total_debits,
           SUM(CASE WHEN credit_amount IS NOT NULL THEN credit_amount ELSE 0 END) as total_credits
    FROM banking_transactions
    WHERE account_number LIKE '%8362'
    AND EXTRACT(YEAR FROM transaction_date) = 2018
""")
count, debits, credits = cur.fetchone()
print(f"Total 2018 transactions: {count}")
print(f"Total debits: ${debits:,.2f}")
print(f"Total credits: ${credits:,.2f}")
print(f"Net: ${credits - debits:,.2f}")

cur.execute("""
    SELECT COUNT(*) 
    FROM banking_transactions
    WHERE account_number LIKE '%8362'
    AND EXTRACT(YEAR FROM transaction_date) = 2018
    AND is_nsf_charge = TRUE
""")
nsf_count = cur.fetchone()[0]
print(f"\nNSF transactions marked: {nsf_count}")

cur.execute("""
    SELECT COUNT(*)
    FROM receipts
    WHERE receipt_date >= '2018-01-01' AND receipt_date < '2019-01-01'
    AND created_from_banking = TRUE
""")
receipt_count = cur.fetchone()[0]
print(f"Receipts created from banking: {receipt_count}")

cur.close()
conn.close()

print("\n✅ COMPLETE")
