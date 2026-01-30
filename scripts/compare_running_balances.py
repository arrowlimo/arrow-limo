#!/usr/bin/env python3
"""
Compare running balances: Database vs Excel
This will identify missing transactions by detecting balance discrepancies
"""

import pandas as pd
import psycopg2

XLSX_FILE = "L:/limo/data/2013_scotia_transactions_for_editingfinal.xlsx"
SCOTIA_ACCOUNT = '903990106011'

print("="*80)
print("DATABASE VS EXCEL RUNNING BALANCE COMPARISON")
print("="*80)

# Load Excel
print("\n📂 Loading Excel file...")
df_excel = pd.read_excel(XLSX_FILE)
df_excel['date'] = pd.to_datetime(df_excel['date'], errors='coerce')
df_excel = df_excel[df_excel['date'].notna()].sort_values('date').reset_index(drop=True)
print(f"✅ Excel: {len(df_excel)} transactions")

# Load Database
print("\n📂 Loading database...")
conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REDACTED***'
)
cur = conn.cursor()

cur.execute("""
    SELECT transaction_id, transaction_date, description, 
           debit_amount, credit_amount, balance
    FROM banking_transactions
    WHERE account_number = %s
      AND EXTRACT(YEAR FROM transaction_date) IN (2013, 2014)
    ORDER BY transaction_date ASC, transaction_id ASC
""", (SCOTIA_ACCOUNT,))

db_rows = cur.fetchall()
df_db = pd.DataFrame(db_rows, columns=['transaction_id', 'date', 'description', 'debit', 'credit', 'balance'])
print(f"✅ Database: {len(df_db)} transactions")

# Calculate running balance for database
print("\n🔢 Calculating database running balance...")
starting_balance = float(df_excel.iloc[0]['balance']) if pd.notna(df_excel.iloc[0]['balance']) else 0.0
print(f"   Starting balance: ${starting_balance:,.2f}")

db_balance = starting_balance
for idx in range(len(df_db)):
    debit = float(df_db.at[idx, 'debit']) if df_db.at[idx, 'debit'] else 0.0
    credit = float(df_db.at[idx, 'credit']) if df_db.at[idx, 'credit'] else 0.0
    db_balance = db_balance + credit - debit
    df_db.at[idx, 'calculated_balance'] = db_balance

# Calculate running balance for Excel
print("🔢 Calculating Excel running balance...")
excel_balance = starting_balance
df_excel['calculated_balance'] = 0.0

for idx in range(len(df_excel)):
    debit = float(df_excel.at[idx, 'debit/withdrawal']) if pd.notna(df_excel.at[idx, 'debit/withdrawal']) else 0.0
    credit = float(df_excel.at[idx, 'deposit/credit']) if pd.notna(df_excel.at[idx, 'deposit/credit']) else 0.0
    excel_balance = excel_balance + credit - debit
    df_excel.at[idx, 'calculated_balance'] = excel_balance

# Compare by date
print(f"\n{'='*80}")
print("COMPARING BALANCES BY DATE")
print(f"{'='*80}")

# Convert date column to datetime if needed
df_db['date'] = pd.to_datetime(df_db['date'])

# Group by date
excel_by_date = df_excel.groupby(df_excel['date'].dt.date).agg({
    'calculated_balance': 'last',
    'balance': 'last'
}).reset_index()
excel_by_date.columns = ['date', 'excel_calculated', 'excel_original']

db_by_date = df_db.groupby(df_db['date'].dt.date).agg({
    'calculated_balance': 'last'
}).reset_index()
db_by_date.columns = ['date', 'db_calculated']

# Merge
comparison = pd.merge(excel_by_date, db_by_date, on='date', how='outer', indicator=True)

# Find discrepancies
discrepancies = []

for idx, row in comparison.iterrows():
    if pd.notna(row['excel_calculated']) and pd.notna(row['db_calculated']):
        diff = abs(row['excel_calculated'] - row['db_calculated'])
        if diff > 0.01:
            discrepancies.append({
                'date': row['date'],
                'excel_balance': row['excel_calculated'],
                'db_balance': row['db_calculated'],
                'difference': diff
            })

# Report results
if len(discrepancies) == 0:
    print("\n✅ ALL BALANCES MATCH PERFECTLY!")
    print("   No missing transactions detected.")
else:
    print(f"\n❌ Found {len(discrepancies)} dates with balance discrepancies")
    print("\nThis indicates MISSING or EXTRA transactions on these dates:")
    print(f"\n{'Date':<12} {'Excel Balance':>15} {'DB Balance':>15} {'Difference':>15}")
    print("-" * 60)
    
    for disc in discrepancies[:50]:
        print(f"{str(disc['date']):<12} ${disc['excel_balance']:>14,.2f} ${disc['db_balance']:>14,.2f} ${disc['difference']:>14,.2f}")

# Check for dates only in Excel or only in DB
excel_only = comparison[comparison['_merge'] == 'left_only']
db_only = comparison[comparison['_merge'] == 'right_only']

if len(excel_only) > 0:
    print(f"\n⚠️  {len(excel_only)} dates exist in Excel but NOT in database:")
    for idx, row in excel_only.head(20).iterrows():
        print(f"   {row['date']}: Excel balance ${row['excel_calculated']:,.2f}")

if len(db_only) > 0:
    print(f"\n⚠️  {len(db_only)} dates exist in database but NOT in Excel:")
    for idx, row in db_only.head(20).iterrows():
        print(f"   {row['date']}: DB balance ${row['db_calculated']:,.2f}")

# Final comparison
print(f"\n{'='*80}")
print("FINAL BALANCE COMPARISON")
print(f"{'='*80}")

excel_final = df_excel.iloc[-1]['calculated_balance']
db_final = df_db.iloc[-1]['calculated_balance']

print(f"Excel final balance (calculated): ${excel_final:,.2f}")
print(f"Database final balance (calculated): ${db_final:,.2f}")
print(f"Difference: ${abs(excel_final - db_final):,.2f}")

if abs(excel_final - db_final) < 0.01:
    print("\n✅ FINAL BALANCES MATCH!")
else:
    print("\n❌ FINAL BALANCES DO NOT MATCH - Missing transactions!")

# Show summary
print(f"\n{'='*80}")
print("TRANSACTION COUNT COMPARISON")
print(f"{'='*80}")

for year in [2013, 2014]:
    excel_year = df_excel[df_excel['date'].dt.year == year]
    db_year = df_db[pd.to_datetime(df_db['date']).dt.year == year]
    
    print(f"\n{year}:")
    print(f"  Excel: {len(excel_year)} transactions")
    print(f"  Database: {len(db_year)} transactions")
    print(f"  Difference: {len(excel_year) - len(db_year)}")

cur.close()
conn.close()
