#!/usr/bin/env python3
"""Import the 22 missing Scotia transactions."""

import psycopg2
import pandas as pd
import hashlib

DB_HOST = "localhost"
DB_NAME = "almsdata"
DB_USER = "postgres"
DB_PASSWORD = os.environ.get("DB_PASSWORD")

# Load missing records
df_missing = pd.read_excel(r"L:\limo\data\scotia_22_missing_transactions.xlsx")

print("=" * 100)
print(f"IMPORTING 22 MISSING SCOTIA TRANSACTIONS")
print("=" * 100)

# Connect to database
conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
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
             source_file, import_batch, category, transaction_hash, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
        """, (
            '903990106011',
            date,
            desc,
            debit,
            credit,
            balance,
            '2012_scotia_transactions_for_editing.xlsx',
            'scotia_22_missing_import_2025-12-10',
            'Unclassified',
            tx_hash
        ))
        
        if cur.rowcount > 0:
            inserted += 1
    
    conn.commit()
    print(f"✓ Imported: {inserted} transactions")
    
    # Verify
    cur.execute("""
        SELECT COUNT(*) FROM banking_transactions
        WHERE account_number = '903990106011'
          AND EXTRACT(YEAR FROM transaction_date) = 2012
    """)
    total_count = cur.fetchone()[0]
    print(f"✓ Database now has: {total_count} Scotia 2012 transactions")
    
except Exception as e:
    conn.rollback()
    print(f"❌ ERROR: {e}")
    import traceback
    traceback.print_exc()

finally:
    cur.close()
    conn.close()

print("=" * 100)
