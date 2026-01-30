#!/usr/bin/env python3
"""
Find the 2 missing transactions in 2014
"""

import pandas as pd
import psycopg2

XLSX_FILE = "L:/limo/data/2013_scotia_transactions_for_editingfinal.xlsx"
SCOTIA_ACCOUNT = '903990106011'

# Load Excel
df_excel = pd.read_excel(XLSX_FILE)
df_excel['date'] = pd.to_datetime(df_excel['date'], errors='coerce')
df_excel = df_excel[df_excel['date'].notna()].sort_values('date').reset_index(drop=True)

# Filter 2014 only
df_2014 = df_excel[df_excel['date'].dt.year == 2014].copy()

print("="*80)
print("2014 TRANSACTIONS AROUND THE DISCREPANCY")
print("="*80)

# Show transactions around 2014-06-23 to 2014-06-30
print("\nTransactions from 2014-06-20 to 2014-07-05:")
print(f"\n{'Row':<5} {'Date':<12} {'Description':<50} {'Debit':>12} {'Credit':>12} {'Balance':>12}")
print("-" * 110)

for idx, row in df_2014.iterrows():
    if pd.Timestamp('2014-06-20') <= row['date'] <= pd.Timestamp('2014-07-05'):
        debit = row['debit/withdrawal'] if pd.notna(row['debit/withdrawal']) else 0.0
        credit = row['deposit/credit'] if pd.notna(row['deposit/credit']) else 0.0
        balance = row['balance'] if pd.notna(row['balance']) else 0.0
        desc = str(row['Description'])[:50]
        
        print(f"{idx:<5} {str(row['date'].date()):<12} {desc:<50} ${debit:>11.2f} ${credit:>11.2f} ${balance:>11.2f}")

# Load database
conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()

cur.execute("""
    SELECT transaction_date, description, debit_amount, credit_amount
    FROM banking_transactions
    WHERE account_number = %s
      AND transaction_date BETWEEN '2014-06-20' AND '2014-07-05'
    ORDER BY transaction_date, transaction_id
""", (SCOTIA_ACCOUNT,))

db_rows = cur.fetchall()

print(f"\n\nDATABASE - Same date range:")
print(f"\n{'Date':<12} {'Description':<50} {'Debit':>12} {'Credit':>12}")
print("-" * 90)

for row in db_rows:
    debit = float(row[2]) if row[2] else 0.0
    credit = float(row[3]) if row[3] else 0.0
    desc = str(row[1])[:50]
    print(f"{str(row[0]):<12} {desc:<50} ${debit:>11.2f} ${credit:>11.2f}")

# Find which are in Excel but not in DB
print(f"\n{'='*80}")
print("IDENTIFYING MISSING TRANSACTIONS")
print(f"{'='*80}")

excel_2014_dates = df_2014[['date', 'Description', 'debit/withdrawal', 'deposit/credit']].copy()
excel_2014_dates['date_only'] = excel_2014_dates['date'].dt.date

# Create signature for comparison
excel_2014_dates['signature'] = (
    excel_2014_dates['date_only'].astype(str) + '|' + 
    excel_2014_dates['Description'].astype(str) + '|' +
    excel_2014_dates['debit/withdrawal'].fillna(0).astype(str) + '|' +
    excel_2014_dates['deposit/credit'].fillna(0).astype(str)
)

db_2014_df = pd.DataFrame(db_rows, columns=['date', 'description', 'debit', 'credit'])
db_2014_df['date_only'] = pd.to_datetime(db_2014_df['date']).dt.date
db_2014_df['signature'] = (
    db_2014_df['date_only'].astype(str) + '|' +
    db_2014_df['description'].astype(str) + '|' +
    db_2014_df['debit'].fillna(0).astype(str) + '|' +
    db_2014_df['credit'].fillna(0).astype(str)
)

# Find missing
excel_sigs = set(excel_2014_dates['signature'])
db_sigs = set(db_2014_df['signature'])
missing_sigs = excel_sigs - db_sigs

print(f"\nMissing transactions from database: {len(missing_sigs)}")

if len(missing_sigs) > 0:
    print("\nThese transactions are in Excel but NOT in database:")
    for sig in missing_sigs:
        matching_row = excel_2014_dates[excel_2014_dates['signature'] == sig].iloc[0]
        debit = matching_row['debit/withdrawal'] if pd.notna(matching_row['debit/withdrawal']) else 0.0
        credit = matching_row['deposit/credit'] if pd.notna(matching_row['deposit/credit']) else 0.0
        
        print(f"\n  Date: {matching_row['date_only']}")
        print(f"  Description: {matching_row['Description']}")
        print(f"  Debit: ${debit:.2f}")
        print(f"  Credit: ${credit:.2f}")

cur.close()
conn.close()
