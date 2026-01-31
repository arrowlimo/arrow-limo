#!/usr/bin/env python3
"""Find the actual context - show transactions near end of 2012."""

import pandas as pd

xlsx_path = r"l:\limo\data\2012_scotia_transactions_for_editing.xlsx"

# Load with pandas
df = pd.read_excel(xlsx_path, sheet_name=0)

print("=" * 100)
print("SCOTIA FILE STRUCTURE ANALYSIS")
print("=" * 100)

# Check date range
print(f"\nTotal rows: {len(df)}")
print(f"\nFirst 5 rows:")
for idx in df.head(5).index:
    row = df.iloc[idx]
    print(f"  Row {idx + 2}: {row['date']} | {row['Description']}")

print(f"\nLast 10 rows:")
for idx in df.tail(10).index:
    row = df.iloc[idx]
    date_str = str(row['date']) if pd.notna(row['date']) else "MISSING"
    desc_str = str(row['Description']) if pd.notna(row['Description']) else "(empty)"
    debit = row['debit/withdrawal'] if pd.notna(row['debit/withdrawal']) else 0
    print(f"  Row {idx + 2}: {date_str[:10]} | {desc_str[:30]:30s} | ${debit:>8.2f}")

# Find last valid 2012 date
df['year'] = pd.to_datetime(df['date'], errors='coerce').dt.year
last_2012_idx = None
for idx in range(len(df) - 1, -1, -1):
    if pd.notna(df.iloc[idx]['year']) and df.iloc[idx]['year'] == 2012:
        last_2012_idx = idx
        break

if last_2012_idx:
    print(f"\n" + "=" * 100)
    print(f"LAST VALID 2012 ENTRY + CONTEXT")
    print("=" * 100)
    
    start = max(0, last_2012_idx - 2)
    end = min(len(df), last_2012_idx + 5)
    
    for idx in range(start, end):
        row = df.iloc[idx]
        marker = " ← LAST 2012 ENTRY" if idx == last_2012_idx else ""
        date_str = str(row['date'])[:10] if pd.notna(row['date']) else "MISSING"
        desc = str(row['Description']) if pd.notna(row['Description']) else "(empty)"
        debit = row['debit/withdrawal'] if pd.notna(row['debit/withdrawal']) else 0
        credit = row['deposit/credit'] if pd.notna(row['deposit/credit']) else 0
        balance = row['balance'] if pd.notna(row['balance']) else 0
        print(f"\nRow {idx + 2}{marker}")
        print(f"  Date: {date_str}")
        print(f"  Description: {desc}")
        print(f"  Debit: ${debit:>8.2f} | Credit: ${credit:>8.2f} | Balance: ${balance:>10.2f}")

# Find where $116.00 is
idx_116 = df[df['debit/withdrawal'] == 116.0].index[0]
print(f"\n" + "=" * 100)
print(f"$116.00 ENTRY IS AT ROW {idx_116 + 2}")
print(f"It's {len(df) - idx_116 - 1} rows from the end")
print("=" * 100)
