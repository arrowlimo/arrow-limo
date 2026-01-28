#!/usr/bin/env python3
"""
Find and import missing Scotia 2014 transactions (June 24 - Dec 29)
"""

import pandas as pd
import psycopg2

XLSX_FILE = "L:/limo/data/2013_scotia_transactions_for_editingfinal.xlsx"
SCOTIA_ACCOUNT = '903990106011'

print("="*80)
print("FINDING MISSING SCOTIA 2014 TRANSACTIONS")
print("="*80)

# Load Excel
df = pd.read_excel(XLSX_FILE)
df['date'] = pd.to_datetime(df['date'], errors='coerce')
df = df[df['date'].notna()]

# Filter for missing date range (after 2014-06-23)
missing_df = df[df['date'] > '2014-06-23']
print(f"\n✅ Found {len(missing_df)} transactions after 2014-06-23")
print(f"   Date range: {missing_df['date'].min().date()} to {missing_df['date'].max().date()}")
print(f"   Total debits: ${missing_df['debit/withdrawal'].sum():,.2f}")
print(f"   Total credits: ${missing_df['deposit/credit'].sum():,.2f}")

# Connect to database
conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REMOVED***'
)
cur = conn.cursor()

# Import missing transactions
print(f"\n📝 Importing {len(missing_df)} missing transactions...")
inserted = 0
errors = 0

for idx, row in missing_df.iterrows():
    try:
        transaction_date = pd.to_datetime(row['date']).date()
        description = str(row['Description']).strip() if pd.notna(row['Description']) else ''
        debit_amount = float(row['debit/withdrawal']) if pd.notna(row['debit/withdrawal']) else None
        credit_amount = float(row['deposit/credit']) if pd.notna(row['deposit/credit']) else None
        balance = float(row['balance']) if pd.notna(row['balance']) else None
        
        cur.execute("""
            INSERT INTO banking_transactions (
                account_number, transaction_date, description,
                debit_amount, credit_amount, balance,
                source_file, import_batch, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
        """, (
            SCOTIA_ACCOUNT,
            transaction_date,
            description,
            debit_amount,
            credit_amount,
            balance,
            'verified_2013_2014_scotia',
            'scotia_missing_2014_import'
        ))
        inserted += 1
        
        if inserted % 100 == 0:
            print(f"   Imported {inserted}...")
            conn.commit()
            
    except Exception as e:
        errors += 1
        if errors <= 3:
            print(f"⚠️  Row {idx}: {e}")

conn.commit()
print(f"\n✅ Import complete: {inserted} inserted, {errors} errors")

# Verify
cur.execute("""
    SELECT COUNT(*) 
    FROM banking_transactions 
    WHERE account_number = %s 
      AND EXTRACT(YEAR FROM transaction_date) IN (2013, 2014)
""", (SCOTIA_ACCOUNT,))
total = cur.fetchone()[0]

print(f"\n📊 Total 2013-2014 Scotia transactions in database: {total}")
print(f"   Expected: 2627")
print(f"   Status: {'✅ MATCH' if total == 2627 else f'❌ Still missing {2627 - total}'}")

cur.close()
conn.close()
