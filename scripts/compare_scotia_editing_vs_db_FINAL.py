#!/usr/bin/env python3
"""Compare 2012_scotia_transactions_for_editing.xlsx (760 rows) to database."""

import psycopg2
import pandas as pd
import os

# Database connection
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

# Load Scotia editing file
xlsx_path = r"L:\limo\data\2012_scotia_transactions_for_editing.xlsx"
df_file = pd.read_excel(xlsx_path, sheet_name=0)

print("=" * 100)
print("2012 SCOTIA TRANSACTIONS FOR EDITING vs DATABASE")
print("=" * 100)

print(f"\nSCOTIA EDITING FILE:")
print(f"  Total rows: {len(df_file)}")
print(f"  Columns: {list(df_file.columns)}")

# Filter to 2012 only
df_file['year'] = pd.to_datetime(df_file['date'], errors='coerce').dt.year
df_file_2012 = df_file[df_file['year'] == 2012].copy()
print(f"  2012 rows: {len(df_file_2012)}")
print(f"  Non-2012 rows: {len(df_file) - len(df_file_2012)}")

# Connect to database
conn = psycopg2.connect(
    host=DB_HOST,
    database=DB_NAME,
    user=DB_USER,
    password=DB_PASSWORD
)
cur = conn.cursor()

# Get Scotia transactions from database (account_number 903990106011)
cur.execute("""
    SELECT transaction_date, description, debit_amount, credit_amount, balance
    FROM banking_transactions
    WHERE account_number = '903990106011'
      AND EXTRACT(YEAR FROM transaction_date) = 2012
    ORDER BY transaction_date, transaction_id
""")
db_rows = cur.fetchall()

print(f"\nDATABASE (Scotia 903990106011, 2012):")
print(f"  Total rows: {len(db_rows)}")

# Create comparable dataframes
df_file_2012['date_normalized'] = pd.to_datetime(df_file_2012['date']).dt.date
df_file_2012['debit'] = pd.to_numeric(df_file_2012['debit/withdrawal'], errors='coerce').fillna(0).round(2)
df_file_2012['credit'] = pd.to_numeric(df_file_2012['deposit/credit'], errors='coerce').fillna(0).round(2)
df_file_2012['balance'] = pd.to_numeric(df_file_2012['balance'], errors='coerce').fillna(0).round(2)
df_file_2012['desc'] = df_file_2012['Description'].fillna('').str.strip().str.upper()

# Create database dataframe
df_db = pd.DataFrame(db_rows, columns=['date', 'description', 'debit', 'credit', 'balance'])
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

matched = file_hashes & db_hashes
in_file_not_db = file_hashes - db_hashes
in_db_not_file = db_hashes - file_hashes

print(f"\nMatching summary:")
print(f"  File records (2012): {len(file_hashes)}")
print(f"  DB records: {len(db_hashes)}")
print(f"  Matched: {len(matched)}")
print(f"  In file but NOT in DB: {len(in_file_not_db)}")
print(f"  In DB but NOT in file: {len(in_db_not_file)}")

if len(in_file_not_db) > 0:
    print(f"\n" + "=" * 100)
    print(f"MISSING FROM DATABASE ({len(in_file_not_db)} records)")
    print("=" * 100)
    missing_from_db = df_file_2012[df_file_2012['hash'].isin(in_file_not_db)].sort_values('date')
    
    print(f"\nThese {len(missing_from_db)} transactions need to be imported:")
    for idx, row in missing_from_db.iterrows():
        print(f"\n  {row['date_normalized']} | {row['desc'][:50]:50s}")
        print(f"    Debit: ${row['debit']:>9.2f} | Credit: ${row['credit']:>9.2f} | Balance: ${row['balance']:>10.2f}")
    
    # Export missing records
    output_path = r"L:\limo\data\scotia_missing_from_db_FINAL.xlsx"
    missing_from_db[['date', 'Description', 'debit/withdrawal', 'deposit/credit', 'balance']].to_excel(output_path, index=False)
    print(f"\n✓ Exported missing records to: {output_path}")

if len(in_db_not_file) > 0:
    print(f"\n" + "=" * 100)
    print(f"IN DATABASE BUT NOT IN FILE ({len(in_db_not_file)} records)")
    print("=" * 100)
    extra_in_db = df_db[df_db['hash'].isin(in_db_not_file)].sort_values('date')
    
    print(f"\nThese {len(extra_in_db)} transactions are in DB but not in your file:")
    for idx, row in extra_in_db.head(10).iterrows():
        print(f"\n  {row['date_normalized']} | {row['desc'][:50]:50s}")
        print(f"    Debit: ${row['debit']:>9.2f} | Credit: ${row['credit']:>9.2f} | Balance: ${row['balance']:>10.2f}")
    
    if len(extra_in_db) > 10:
        print(f"\n  ... and {len(extra_in_db) - 10} more")

# Check the $116.00 entry specifically
print(f"\n" + "=" * 100)
print("$116.00 RUN'N ON EMPTY ENTRY CHECK")
print("=" * 100)

entry_116_file = df_file_2012[(df_file_2012['debit'] == 116.0)]
entry_116_db = df_db[(df_db['debit'] == 116.0)]

print(f"  In file: {len(entry_116_file)} match(es)")
if len(entry_116_file) > 0:
    for idx, row in entry_116_file.iterrows():
        print(f"    {row['date_normalized']} | {row['desc']} | ${row['debit']:.2f}")

print(f"  In database: {len(entry_116_db)} match(es)")
if len(entry_116_db) > 0:
    for idx, row in entry_116_db.iterrows():
        print(f"    {row['date_normalized']} | {row['desc']} | ${row['debit']:.2f}")

print(f"\n" + "=" * 100)
print("SUMMARY & RECOMMENDATION")
print("=" * 100)
print(f"  File 2012 transactions: {len(df_file_2012)}")
print(f"  Database transactions: {len(df_db)}")
print(f"  Difference: {len(df_file_2012) - len(df_db)}")
print(f"  Missing from DB: {len(in_file_not_db)}")

if len(in_file_not_db) > 0:
    print(f"\n⚠️  ACTION REQUIRED:")
    print(f"     Delete existing {len(df_db)} Scotia 2012 transactions from database")
    print(f"     Import all {len(df_file_2012)} transactions from file")
    print(f"     This will add {len(in_file_not_db)} new transactions")

cur.close()
conn.close()
