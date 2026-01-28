#!/usr/bin/env python3
"""Import the 2 missing Scotia transactions to database."""

import psycopg2
import pandas as pd
import os
import hashlib

# Database connection
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

# Load missing records
missing_file = r"L:\limo\data\scotia_missing_from_db_FINAL.xlsx"
df_missing = pd.read_excel(missing_file)

print("=" * 100)
print("IMPORTING 2 MISSING SCOTIA TRANSACTIONS")
print("=" * 100)

print(f"\nRecords to import:")
for idx, row in df_missing.iterrows():
    date = pd.to_datetime(row['date']).date()
    desc = row['Description']
    debit = row['debit/withdrawal'] if pd.notna(row['debit/withdrawal']) else 0
    credit = row['deposit/credit'] if pd.notna(row['deposit/credit']) else 0
    balance = row['balance']
    print(f"  {date} | {desc:30s} | Debit: ${debit:>8.2f} | Credit: ${credit:>8.2f} | Balance: ${balance:>10.2f}")

# Connect to database
conn = psycopg2.connect(
    host=DB_HOST,
    database=DB_NAME,
    user=DB_USER,
    password=DB_PASSWORD
)
cur = conn.cursor()

try:
    inserted = 0
    for idx, row in df_missing.iterrows():
        date = pd.to_datetime(row['date']).date()
        desc = row['Description']
        debit = float(row['debit/withdrawal']) if pd.notna(row['debit/withdrawal']) else 0
        credit = float(row['deposit/credit']) if pd.notna(row['deposit/credit']) else 0
        balance = float(row['balance']) if pd.notna(row['balance']) else 0
        
        # Create transaction hash
        hash_input = f"903990106011|{date}|{desc}|{debit}|{credit}".encode('utf-8')
        tx_hash = hashlib.sha256(hash_input).hexdigest()
        
        # Insert into banking_transactions
        cur.execute("""
            INSERT INTO banking_transactions 
            (account_number, transaction_date, description, debit_amount, credit_amount, balance, 
             source_file, import_batch, category, transaction_hash, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
        """, (
            '903990106011',
            date,
            desc,
            debit,
            credit,
            balance,
            '2012_scotia_transactions_for_editing.xlsx',
            'scotia_missing_import_2025-12-10',
            'Unclassified',
            tx_hash
        ))
        
        if cur.rowcount > 0:
            inserted += 1
            print(f"\n✓ Inserted: {date} | {desc} | ${debit if debit > 0 else credit:.2f}")
        else:
            print(f"\n⊘ Already exists: {date} | {desc}")
    
    conn.commit()
    print(f"\n" + "=" * 100)
    print(f"✓ IMPORT COMPLETE: {inserted} transactions inserted")
    print("=" * 100)
    
    # Verify
    cur.execute("""
        SELECT COUNT(*) FROM banking_transactions
        WHERE account_number = '903990106011'
          AND EXTRACT(YEAR FROM transaction_date) = 2012
    """)
    total_count = cur.fetchone()[0]
    print(f"\nDatabase now has: {total_count} Scotia 2012 transactions")
    
except Exception as e:
    conn.rollback()
    print(f"\n❌ ERROR: {e}")
    import traceback
    traceback.print_exc()

finally:
    cur.close()
    conn.close()
