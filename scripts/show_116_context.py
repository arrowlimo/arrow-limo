#!/usr/bin/env python3
"""Find rows immediately before and after the $116.00 entry."""

import pandas as pd

xlsx_path = r"l:\limo\data\2012_scotia_transactions_for_editing.xlsx"

# Load with pandas
df = pd.read_excel(xlsx_path, sheet_name=0)

# Find the row with $116.00 debit
row_116 = df[df['debit/withdrawal'] == 116.0]

if len(row_116) > 0:
    idx_116 = row_116.index[0]
    
    print("=" * 100)
    print("ROWS SURROUNDING THE $116.00 ENTRY")
    print("=" * 100)
    
    # Get rows around it (before, the entry itself, after)
    start_idx = max(0, idx_116 - 2)
    end_idx = min(len(df), idx_116 + 3)
    
    context_df = df.iloc[start_idx:end_idx].copy()
    
    for i, (idx, row) in enumerate(context_df.iterrows()):
        row_num = idx + 2  # Account for header row
        marker = " ← $116.00 ENTRY" if idx == idx_116 else ""
        
        date_val = str(row['date']) if pd.notna(row['date']) else "MISSING DATE"
        desc_val = str(row['Description']) if pd.notna(row['Description']) else "(no description)"
        debit = float(row['debit/withdrawal']) if pd.notna(row['debit/withdrawal']) else 0
        credit = float(row['deposit/credit']) if pd.notna(row['deposit/credit']) else 0
        balance = float(row['balance']) if pd.notna(row['balance']) else 0
        
        print(f"\nRow {row_num}{marker}")
        print(f"  Date: {date_val}")
        print(f"  Description: {desc_val}")
        print(f"  Debit: ${debit:.2f}")
        print(f"  Credit: ${credit:.2f}")
        print(f"  Balance: ${balance:.2f}")
    
    print("\n" + "=" * 100)
    
else:
    print("ERROR: $116.00 entry not found!")
