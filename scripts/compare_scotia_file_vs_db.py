#!/usr/bin/env python3
"""Compare Scotia editing file vs database to find missing/mismatched records."""

import psycopg2
import pandas as pd
import os
from datetime import datetime

# Database connection
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

# Load Scotia file
xlsx_path = r"l:\limo\data\2012_scotia_transactions_for_editing.xlsx"
df_file = pd.read_excel(xlsx_path, sheet_name=0)

print("=" * 100)
print("SCOTIA FILE vs DATABASE COMPARISON")
print("=" * 100)

print(f"\nSCOTIA FILE:")
print(f"  Total rows: {len(df_file)}")
df_file['year'] = pd.to_datetime(df_file['date'], errors='coerce').dt.year
print(f"  2012 rows: {len(df_file[df_file['year'] == 2012])}")
print(f"  2015 rows: {len(df_file[df_file['year'] == 2015])}")
print(f"  2019 rows: {len(df_file[df_file['year'] == 2019])}")

# Connect to database
conn = psycopg2.connect(
    host=DB_HOST,
    database=DB_NAME,
    user=DB_USER,
    password=DB_PASSWORD
)
cur = conn.cursor()

# Get Scotia transactions from database
cur.execute("""
    SELECT transaction_date, description, debit_amount, credit_amount, balance
    FROM banking_transactions
    WHERE mapped_bank_account_id = 2
      AND EXTRACT(YEAR FROM transaction_date) = 2012
    ORDER BY transaction_date, banking_transaction_id
""")
db_rows = cur.fetchall()

print(f"\nDATABASE (Scotia 2012):")
print(f"  Total rows: {len(db_rows)}")

# Create comparable dataframes
df_file_2012 = df_file[df_file['year'] == 2012].copy()
df_file_2012['date_normalized'] = pd.to_datetime(df_file_2012['date']).dt.date
df_file_2012['debit'] = df_file_2012['debit/withdrawal'].fillna(0).round(2)
df_file_2012['credit'] = df_file_2012['deposit/credit'].fillna(0).round(2)
df_file_2012['balance'] = df_file_2012['balance'].fillna(0).round(2)
df_file_2012['desc'] = df_file_2012['Description'].fillna('').str.strip()

# Create database dataframe
df_db = pd.DataFrame(db_rows, columns=['date', 'description', 'debit', 'credit', 'balance'])
df_db['date_normalized'] = pd.to_datetime(df_db['date']).dt.date
df_db['debit'] = df_db['debit'].fillna(0).round(2)
df_db['credit'] = df_db['credit'].fillna(0).round(2)
df_db['balance'] = df_db['balance'].fillna(0).round(2)
df_db['desc'] = df_db['description'].fillna('').str.strip()

print(f"\n" + "=" * 100)
print("MATCHING ANALYSIS")
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

print(f"\nIN FILE BUT NOT IN DATABASE: {len(in_file_not_db)}")
if len(in_file_not_db) > 0:
    print(f"\nThese {len(in_file_not_db)} transactions are in the Excel file but missing from database:")
    missing_from_db = df_file_2012[df_file_2012['hash'].isin(in_file_not_db)]
    for idx, row in missing_from_db.iterrows():
        print(f"\n  {row['date_normalized']} | {row['desc'][:40]:40s}")
        print(f"    Debit: ${row['debit']:>8.2f} | Credit: ${row['credit']:>8.2f} | Balance: ${row['balance']:>10.2f}")

print(f"\nIN DATABASE BUT NOT IN FILE: {len(in_db_not_file)}")
if len(in_db_not_file) > 0:
    print(f"\nThese {len(in_db_not_file)} transactions are in database but not in Excel file:")
    missing_from_file = df_db[df_db['hash'].isin(in_db_not_file)]
    for idx, row in missing_from_file.iterrows():
        print(f"\n  {row['date_normalized']} | {row['desc'][:40]:40s}")
        print(f"    Debit: ${row['debit']:>8.2f} | Credit: ${row['credit']:>8.2f} | Balance: ${row['balance']:>10.2f}")

# Check if the $116.00 entry is in the database now
entry_116_in_file = df_file_2012[(df_file_2012['debit'] == 116.0) & (df_file_2012['date_normalized'] == datetime(2012, 12, 3).date())]
entry_116_in_db = df_db[(df_db['debit'] == 116.0) & (df_db['date_normalized'] == datetime(2012, 12, 3).date())]

print(f"\n" + "=" * 100)
print("$116.00 ENTRY STATUS")
print("=" * 100)
print(f"  In file: {len(entry_116_in_file) > 0} ({len(entry_116_in_file)} matches)")
print(f"  In database: {len(entry_116_in_db) > 0} ({len(entry_116_in_db)} matches)")

print(f"\n" + "=" * 100)
print("SUMMARY")
print("=" * 100)
print(f"  File (2012 only): {len(df_file_2012)} transactions")
print(f"  Database: {len(df_db)} transactions")
print(f"  Difference: {len(df_file_2012) - len(df_db)}")
print(f"  Missing from DB: {len(in_file_not_db)}")
print(f"  Extra in DB: {len(in_db_not_file)}")

cur.close()
conn.close()
