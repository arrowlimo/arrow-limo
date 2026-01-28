#!/usr/bin/env python3
"""
Validate running balance column from Excel file
Calculate balance from first transaction and verify against Excel balances
"""

import pandas as pd

XLSX_FILE = "L:/limo/data/2013_scotia_transactions_for_editingfinal.xlsx"

print("="*80)
print("SCOTIA 2013-2014 RUNNING BALANCE VALIDATION")
print("="*80)

# Load Excel
df = pd.read_excel(XLSX_FILE)
df['date'] = pd.to_datetime(df['date'], errors='coerce')
df = df[df['date'].notna()].sort_values('date').reset_index(drop=True)

print(f"\n✅ Loaded {len(df)} transactions")
print(f"   Date range: {df['date'].min().date()} to {df['date'].max().date()}")

# Starting balance from first row
starting_balance = float(df.iloc[0]['balance']) if pd.notna(df.iloc[0]['balance']) else 0.0
print(f"\n📊 Starting balance: ${starting_balance:,.2f}")

# Validate running balance
errors = []
calculated_balance = starting_balance

print(f"\n{'='*80}")
print("VALIDATING RUNNING BALANCES")
print(f"{'='*80}")
print("\nFirst 10 transactions:")

for idx, row in df.iterrows():
    debit = float(row['debit/withdrawal']) if pd.notna(row['debit/withdrawal']) else 0.0
    credit = float(row['deposit/credit']) if pd.notna(row['deposit/credit']) else 0.0
    excel_balance = float(row['balance']) if pd.notna(row['balance']) else 0.0
    
    # For first transaction, use the balance as-is
    if idx == 0:
        calculated_balance = excel_balance
        if idx < 10:
            print(f"  Row {idx}: {row['date'].date()} | Balance: ${excel_balance:,.2f} (starting)")
        continue
    
    # Calculate expected balance: previous balance + credits - debits
    expected_balance = calculated_balance + credit - debit
    
    # Check if it matches Excel
    difference = abs(expected_balance - excel_balance)
    
    if idx < 10:
        status = "✅" if difference < 0.01 else "❌"
        print(f"  Row {idx}: {row['date'].date()} | Excel: ${excel_balance:,.2f}, Calculated: ${expected_balance:,.2f} {status}")
    
    if difference > 0.01:
        errors.append({
            'row': idx,
            'date': row['date'].date(),
            'description': row['Description'],
            'debit': debit,
            'credit': credit,
            'excel_balance': excel_balance,
            'calculated_balance': expected_balance,
            'difference': difference
        })
    
    # Use Excel balance as the next starting point (to avoid accumulating errors)
    calculated_balance = excel_balance

# Report results
print(f"\n{'='*80}")
print("VALIDATION RESULTS")
print(f"{'='*80}")

if len(errors) == 0:
    print("\n✅ ALL BALANCES ARE CORRECT!")
    print("   Every transaction's balance matches the calculated running balance.")
else:
    print(f"\n❌ Found {len(errors)} balance discrepancies:")
    print("\nFirst 20 errors:")
    for error in errors[:20]:
        print(f"\nRow {error['row']}: {error['date']}")
        print(f"  Description: {error['description'][:60]}")
        print(f"  Debit: ${error['debit']:,.2f}, Credit: ${error['credit']:,.2f}")
        print(f"  Excel Balance: ${error['excel_balance']:,.2f}")
        print(f"  Calculated Balance: ${error['calculated_balance']:,.2f}")
        print(f"  Difference: ${error['difference']:,.2f}")

# Summary by year
print(f"\n{'='*80}")
print("SUMMARY BY YEAR")
print(f"{'='*80}")

for year in [2013, 2014]:
    year_df = df[df['date'].dt.year == year]
    year_errors = [e for e in errors if e['date'].year == year]
    
    print(f"\n{year}:")
    print(f"  Total transactions: {len(year_df)}")
    print(f"  Balance errors: {len(year_errors)}")
    print(f"  Accuracy: {((len(year_df) - len(year_errors)) / len(year_df) * 100):.2f}%")

# Check last few transactions
print(f"\n{'='*80}")
print("LAST 10 TRANSACTIONS")
print(f"{'='*80}")

for idx, row in df.tail(10).iterrows():
    debit = float(row['debit/withdrawal']) if pd.notna(row['debit/withdrawal']) else 0.0
    credit = float(row['deposit/credit']) if pd.notna(row['deposit/credit']) else 0.0
    balance = float(row['balance']) if pd.notna(row['balance']) else 0.0
    
    print(f"Row {idx}: {row['date'].date()} | Balance: ${balance:,.2f} | D: ${debit:.2f}, C: ${credit:.2f}")

print(f"\n{'='*80}")
