#!/usr/bin/env python3
"""Compare scotia_2012_transactions_updated.xlsx to database and find missing records."""

import psycopg2
import pandas as pd
import os

# Database connection
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

# Load Scotia updated file
xlsx_path = r"L:\limo\data\scotia_2012_transactions_updated.xlsx"
df_file = pd.read_excel(xlsx_path, sheet_name=0)

print("=" * 100)
print("SCOTIA UPDATED FILE vs DATABASE COMPARISON")
print("=" * 100)

print(f"\nSCOTIA UPDATED FILE:")
print(f"  Total rows: {len(df_file)}")
print(f"  Columns: {list(df_file.columns)}")

# Filter to 2012 only
df_file['year'] = pd.to_datetime(df_file['date'], errors='coerce').dt.year
df_file_2012 = df_file[df_file['year'] == 2012].copy()
print(f"  2012 rows: {len(df_file_2012)}")

# Connect to database
conn = psycopg2.connect(
    host=DB_HOST,
    database=DB_NAME,
    user=DB_USER,
    password=DB_PASSWORD
)
cur = conn.cursor()

# First, check the banking_transactions table structure
cur.execute("""
    SELECT column_name 
    FROM information_schema.columns 
    WHERE table_name = 'banking_transactions' 
    ORDER BY ordinal_position
""")
columns = [row[0] for row in cur.fetchall()]
print(f"\nDATABASE banking_transactions columns:")
for col in columns:
    print(f"  - {col}")

# Get Scotia transactions from database
# Check if we have bank_account_id or account_id column
if 'bank_account_id' in columns:
    account_col = 'bank_account_id'
elif 'account_id' in columns:
    account_col = 'account_id'
else:
    # Try to find Scotia by description or other means
    account_col = None

if account_col:
    cur.execute(f"""
        SELECT transaction_date, description, debit_amount, credit_amount, balance
        FROM banking_transactions
        WHERE {account_col} = 2
          AND EXTRACT(YEAR FROM transaction_date) = 2012
        ORDER BY transaction_date, banking_transaction_id
    """)
else:
    # Fall back to finding Scotia by account_number (903990106011)
    print("\n⚠️  No account_id column found, using account_number to find Scotia...")
    cur.execute("""
        SELECT transaction_date, description, debit_amount, credit_amount, balance,
               transaction_id
        FROM banking_transactions
        WHERE account_number = '903990106011'
          AND EXTRACT(YEAR FROM transaction_date) = 2012
        ORDER BY transaction_date, transaction_id
    """)

db_rows = cur.fetchall()

print(f"\nDATABASE 2012 TRANSACTIONS:")
print(f"  Total rows retrieved: {len(db_rows)}")

# Create comparable dataframes
df_file_2012['date_normalized'] = pd.to_datetime(df_file_2012['date']).dt.date
df_file_2012['debit'] = df_file_2012['debit'].fillna(0).round(2)
df_file_2012['credit'] = df_file_2012['credit'].fillna(0).round(2)
df_file_2012['balance'] = df_file_2012['balance'].fillna(0).round(2)
df_file_2012['desc'] = df_file_2012['description'].fillna('').str.strip().str.upper()

# Create database dataframe
if account_col:
    df_db = pd.DataFrame(db_rows, columns=['date', 'description', 'debit', 'credit', 'balance'])
else:
    df_db = pd.DataFrame(db_rows, columns=['date', 'description', 'debit', 'credit', 'balance', 'transaction_id'])

df_db['date_normalized'] = pd.to_datetime(df_db['date']).dt.date
df_db['debit'] = pd.to_numeric(df_db['debit'], errors='coerce').fillna(0).round(2)
df_db['credit'] = pd.to_numeric(df_db['credit'], errors='coerce').fillna(0).round(2)
df_db['balance'] = pd.to_numeric(df_db['balance'], errors='coerce').fillna(0).round(2)
df_db['desc'] = df_db['description'].fillna('').str.strip().str.upper()

print(f"\n" + "=" * 100)
print("MATCHING ANALYSIS (by date + debit + credit + balance)")
print("=" * 100)

# Create hash for matching
df_file_2012['hash'] = df_file_2012.apply(
    lambda x: f"{x['date_normalized']}|{x['debit']}|{x['credit']}|{x['balance']}", axis=1
)
df_db['hash'] = df_db.apply(
    lambda x: f"{x['date_normalized']}|{x['debit']}|{x['credit']}|{x['balance']}", axis=1
)

file_hashes = set(df_file_2012['hash'])
db_hashes = set(df_db['hash'])

in_file_not_db = file_hashes - db_hashes
in_db_not_file = db_hashes - file_hashes

print(f"\nMatching summary:")
print(f"  File records: {len(file_hashes)}")
print(f"  DB records: {len(db_hashes)}")
print(f"  Matched: {len(file_hashes & db_hashes)}")
print(f"  In file but NOT in DB: {len(in_file_not_db)}")
print(f"  In DB but NOT in file: {len(in_db_not_file)}")

if len(in_file_not_db) > 0:
    print(f"\n" + "=" * 100)
    print(f"MISSING FROM DATABASE ({len(in_file_not_db)} records)")
    print("=" * 100)
    missing_from_db = df_file_2012[df_file_2012['hash'].isin(in_file_not_db)].sort_values('date')
    
    for idx, row in missing_from_db.head(20).iterrows():
        print(f"\n  {row['date_normalized']} | {row['desc'][:50]:50s}")
        print(f"    Debit: ${row['debit']:>9.2f} | Credit: ${row['credit']:>9.2f} | Balance: ${row['balance']:>10.2f}")
    
    if len(missing_from_db) > 20:
        print(f"\n  ... and {len(missing_from_db) - 20} more")
    
    # Export missing records
    output_path = r"L:\limo\data\scotia_missing_from_db.xlsx"
    missing_from_db[['date', 'description', 'debit', 'credit', 'balance']].to_excel(output_path, index=False)
    print(f"\n✓ Exported missing records to: {output_path}")

if len(in_db_not_file) > 0:
    print(f"\n" + "=" * 100)
    print(f"IN DATABASE BUT NOT IN FILE ({len(in_db_not_file)} records)")
    print("=" * 100)
    extra_in_db = df_db[df_db['hash'].isin(in_db_not_file)].sort_values('date')
    
    for idx, row in extra_in_db.head(20).iterrows():
        print(f"\n  {row['date_normalized']} | {row['desc'][:50]:50s}")
        print(f"    Debit: ${row['debit']:>9.2f} | Credit: ${row['credit']:>9.2f} | Balance: ${row['balance']:>10.2f}")
    
    if len(extra_in_db) > 20:
        print(f"\n  ... and {len(extra_in_db) - 20} more")

print(f"\n" + "=" * 100)
print("SUMMARY")
print("=" * 100)
print(f"  Scotia updated file (2012): {len(df_file_2012)} transactions")
print(f"  Database (2012): {len(df_db)} transactions")
print(f"  Missing from DB: {len(in_file_not_db)}")
print(f"  Need to import: {len(in_file_not_db)} records")

cur.close()
conn.close()
