#!/usr/bin/env python3
"""Trace balance flow to find where $116.00 entry belongs chronologically."""

import pandas as pd

xlsx_path = r"l:\limo\data\2012_scotia_transactions_for_editing.xlsx"

# Load with pandas
df = pd.read_excel(xlsx_path, sheet_name=0)

print("=" * 100)
print("BALANCE FLOW ANALYSIS - Finding where $116.00 fits")
print("=" * 100)

# Get the $116.00 entry
row_116 = df[df['debit/withdrawal'] == 116.0].iloc[0]
balance_after_116 = row_116['balance']

print(f"\n$116.00 ENTRY:")
print(f"  Debit: $116.00")
print(f"  Balance AFTER: ${balance_after_116:.2f}")
print(f"  Expected Balance BEFORE: ${balance_after_116 + 116.00:.2f}")

target_balance_before = balance_after_116 + 116.00

print(f"\n" + "=" * 100)
print(f"SEARCHING FOR TRANSACTION WITH BALANCE = ${target_balance_before:.2f}")
print("=" * 100)

# Find transactions with that balance
matches = df[abs(df['balance'] - target_balance_before) < 0.01]

if len(matches) > 0:
    print(f"\nFound {len(matches)} transaction(s) with balance ${target_balance_before:.2f}:")
    for idx in matches.index:
        row = df.iloc[idx]
        date_str = str(row['date'])[:10] if pd.notna(row['date']) else "MISSING"
        desc = str(row['Description']) if pd.notna(row['Description']) else "(empty)"
        debit = row['debit/withdrawal'] if pd.notna(row['debit/withdrawal']) else 0
        credit = row['deposit/credit'] if pd.notna(row['deposit/credit']) else 0
        balance = row['balance']
        
        print(f"\n  Row {idx + 2}:")
        print(f"    Date: {date_str}")
        print(f"    Description: {desc}")
        print(f"    Debit: ${debit:.2f} | Credit: ${credit:.2f}")
        print(f"    Balance: ${balance:.2f}")
        
        # Show what comes after
        if idx + 1 < len(df):
            next_row = df.iloc[idx + 1]
            next_date = str(next_row['date'])[:10] if pd.notna(next_row['date']) else "MISSING"
            next_desc = str(next_row['Description']) if pd.notna(next_row['Description']) else "(empty)"
            next_balance = next_row['balance']
            print(f"\n  NEXT Row {idx + 3}:")
            print(f"    Date: {next_date}")
            print(f"    Description: {next_desc}")
            print(f"    Balance: ${next_balance:.2f}")
            
            print(f"\n  → $116.00 DEBIT should go BETWEEN rows {idx + 2} and {idx + 3}")
            print(f"  → Expected date: Same as or shortly after {date_str}")
else:
    print("\nNo exact match found. Showing closest balances:")
    df['balance_diff'] = abs(df['balance'] - target_balance_before)
    closest = df.nsmallest(5, 'balance_diff')
    
    for idx in closest.index:
        row = df.iloc[idx]
        date_str = str(row['date'])[:10] if pd.notna(row['date']) else "MISSING"
        desc = str(row['Description'])[:40] if pd.notna(row['Description']) else "(empty)"
        balance = row['balance']
        diff = abs(balance - target_balance_before)
        print(f"\n  Row {idx + 2}: {date_str} | {desc:40s} | Balance: ${balance:.2f} (diff: ${diff:.2f})")

print("\n" + "=" * 100)
