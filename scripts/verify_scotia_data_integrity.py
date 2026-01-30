#!/usr/bin/env python3
"""
Verify Scotia 2013-2014 data integrity and running balances
Compare Excel file vs Database
"""

import pandas as pd
import psycopg2
from datetime import datetime

XLSX_FILE = "L:/limo/data/2013_scotia_transactions_for_editingfinal.xlsx"
SCOTIA_ACCOUNT = '903990106011'

print("="*80)
print("SCOTIA 2013-2014 DATA VERIFICATION")
print("="*80)

# Load Excel file
print("\n📂 Loading Excel file...")
df_excel = pd.read_excel(XLSX_FILE, sheet_name=0)
df_excel['date'] = pd.to_datetime(df_excel['date'], errors='coerce')
df_excel = df_excel[df_excel['date'].notna()]  # Remove invalid dates
df_excel = df_excel.sort_values('date')
print(f"✅ Excel: {len(df_excel)} transactions")
print(f"   Date range: {df_excel['date'].min().date()} to {df_excel['date'].max().date()}")

# Load database
print("\n📂 Loading database...")
conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REDACTED***'
)
cur = conn.cursor()

cur.execute("""
    SELECT transaction_date, description, debit_amount, credit_amount, balance
    FROM banking_transactions
    WHERE account_number = %s
      AND EXTRACT(YEAR FROM transaction_date) IN (2013, 2014)
    ORDER BY transaction_date ASC, transaction_id ASC
""", (SCOTIA_ACCOUNT,))

db_rows = cur.fetchall()
df_db = pd.DataFrame(db_rows, columns=['date', 'description', 'debit', 'credit', 'balance'])
print(f"✅ Database: {len(df_db)} transactions")
print(f"   Date range: {df_db['date'].min()} to {df_db['date'].max()}")

# Compare counts
print(f"\n{'='*80}")
print("COUNT COMPARISON")
print(f"{'='*80}")
print(f"Excel file:  {len(df_excel)} transactions")
print(f"Database:    {len(df_db)} transactions")
print(f"Difference:  {len(df_excel) - len(df_db)} {'❌ MISMATCH' if len(df_excel) != len(df_db) else '✅ MATCH'}")

# Compare totals
print(f"\n{'='*80}")
print("AMOUNT TOTALS COMPARISON")
print(f"{'='*80}")

excel_debits = float(df_excel['debit/withdrawal'].sum())
excel_credits = float(df_excel['deposit/credit'].sum())
db_debits = float(df_db['debit'].sum())
db_credits = float(df_db['credit'].sum())

print(f"Excel Debits:     ${excel_debits:,.2f}")
print(f"Database Debits:  ${db_debits:,.2f}")
print(f"Difference:       ${excel_debits - db_debits:,.2f} {'❌' if abs(excel_debits - db_debits) > 0.01 else '✅'}")

print(f"\nExcel Credits:    ${excel_credits:,.2f}")
print(f"Database Credits: ${db_credits:,.2f}")
print(f"Difference:       ${excel_credits - db_credits:,.2f} {'❌' if abs(excel_credits - db_credits) > 0.01 else '✅'}")

# Verify running balances
print(f"\n{'='*80}")
print("RUNNING BALANCE VERIFICATION")
print(f"{'='*80}")

balance_errors = 0
last_balance_check = None

# Check first 10 and last 10 transactions
print("\nFirst 5 transactions:")
for idx, row in df_db.head(5).iterrows():
    debit = float(row['debit']) if row['debit'] else 0.0
    credit = float(row['credit']) if row['credit'] else 0.0
    balance = float(row['balance']) if row['balance'] else 0.0
    print(f"  {row['date']}: Balance ${balance:,.2f} | Debit: ${debit:.2f}, Credit: ${credit:.2f}")

print("\nLast 5 transactions:")
for idx, row in df_db.tail(5).iterrows():
    debit = float(row['debit']) if row['debit'] else 0.0
    credit = float(row['credit']) if row['credit'] else 0.0
    balance = float(row['balance']) if row['balance'] else 0.0
    print(f"  {row['date']}: Balance ${balance:,.2f} | Debit: ${debit:.2f}, Credit: ${credit:.2f}")

# Check for balance calculation errors
print(f"\n{'='*80}")
print("BALANCE CALCULATION CHECK")
print(f"{'='*80}")

calculated_balance = None
for idx, row in df_db.iterrows():
    if calculated_balance is None:
        calculated_balance = row['balance']
    else:
        # Calculate expected balance
        change = (row['credit'] if row['credit'] else 0) - (row['debit'] if row['debit'] else 0)
        expected_balance = calculated_balance + change
        
        # Check if it matches
        if abs(expected_balance - row['balance']) > 0.01:
            balance_errors += 1
            if balance_errors <= 5:
                print(f"❌ Balance mismatch at {row['date']}: Expected ${expected_balance:.2f}, Got ${row['balance']:.2f}")
        
        calculated_balance = row['balance']

if balance_errors == 0:
    print("✅ All running balances are correct")
else:
    print(f"\n⚠️  Found {balance_errors} balance calculation errors")

# Find missing transactions
print(f"\n{'='*80}")
print("MISSING TRANSACTION CHECK")
print(f"{'='*80}")

# Group by date and count
excel_by_date = df_excel.groupby(df_excel['date'].dt.date).size()
db_by_date = df_db.groupby(df_db['date'].dt.date).size()

missing_dates = []
for date, count in excel_by_date.items():
    db_count = db_by_date.get(date, 0)
    if db_count < count:
        missing_dates.append((date, count - db_count))

if missing_dates:
    print(f"⚠️  Found {len(missing_dates)} dates with missing transactions:")
    for date, missing_count in missing_dates[:10]:
        print(f"   {date}: Missing {missing_count} transaction(s)")
        # Show which transactions are missing
        excel_on_date = df_excel[df_excel['date'].dt.date == date]
        print(f"      Excel has {len(excel_on_date)} transactions on this date")
else:
    print("✅ No missing dates found")

# Year breakdown
print(f"\n{'='*80}")
print("YEAR BREAKDOWN")
print(f"{'='*80}")

for year in [2013, 2014]:
    excel_year = df_excel[df_excel['date'].dt.year == year]
    db_year = df_db[pd.to_datetime(df_db['date']).dt.year == year]
    
    excel_debits_year = float(excel_year['debit/withdrawal'].sum())
    excel_credits_year = float(excel_year['deposit/credit'].sum())
    db_debits_year = float(db_year['debit'].sum())
    db_credits_year = float(db_year['credit'].sum())
    
    print(f"\n{year}:")
    print(f"  Excel:    {len(excel_year)} transactions (Debits: ${excel_debits_year:,.2f}, Credits: ${excel_credits_year:,.2f})")
    print(f"  Database: {len(db_year)} transactions (Debits: ${db_debits_year:,.2f}, Credits: ${db_credits_year:,.2f})")
    print(f"  Status:   {'✅ MATCH' if len(excel_year) == len(db_year) else '❌ MISMATCH'}")

cur.close()
conn.close()

print(f"\n{'='*80}")
print("VERIFICATION COMPLETE")
print(f"{'='*80}")
