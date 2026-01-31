#!/usr/bin/env python3
"""
Find the 6 mismatches in workbook by searching for the parent receipt IDs.
"""
import pandas as pd
from pathlib import Path

path = Path(r"L:\limo\reports\receipts table layout.xlsx")
df = pd.read_excel(path, sheet_name='receipts')

# Convert to numeric, handling NaN
df['id'] = pd.to_numeric(df['id'], errors='coerce')

# The 6 parent receipt IDs from DB
parent_ids = [1044, 1222, 1238, 1330, 1537, 1618, 1747]

print("=" * 150)
print("2019 SPLIT RECEIPT MISMATCHES - Workbook Rows by Receipt ID")
print("=" * 150)

for parent_id in parent_ids:
    subset = df[df['id'] == float(parent_id)]
    
    if subset.empty:
        print(f"\nParent ID {parent_id}: NOT FOUND in workbook")
        continue
    
    print(f"\nParent ID {parent_id}:")
    print("-" * 150)
    
    cols_to_show = ['id','receipt_date','vendor_name','revenue','expense','payment_method','card_number','card_type','comment']
    cols_avail = [c for c in cols_to_show if c in subset.columns]
    
    for idx, row in subset.iterrows():
        row_info = " | ".join([f"{col}={row[col]}" for col in cols_avail])
        print(f"  {row_info}")

print("\n" + "=" * 150)
print("6 MISMATCHES REQUIRING CORRECTION:")
print("=" * 150)
print("""
1044 | 2019-02-26 | RUN'N ON EMPTY      | split 62.75 vs combined 62.50 (diff -0.25)
1222 | 2019-05-11 | FAS GAS             | split 77.66 vs combined 67.66 (diff -10.00) ← LARGE
1238 | 2019-05-16 | RUN'N ON EMPTY      | split 48.35 vs combined 48.95 (diff +0.60)
1330 | 2019-06-15 | SPRINGS LIQUOR      | split 106.25 vs combined 106.00 (diff -0.25)
1537 | 2019-09-06 | RUN'N ON EMPTY      | split 54.57 vs combined 54.56 (diff -0.01) ← Minor
1618 | 2019-10-14 | FAS GAS             | split 24.25 vs combined 34.25 (diff +10.00) ← LARGE

ACTION: Review workbook rows above for payment_method, card_type, revenue clues.
→ Leave as-is for now per user instruction (totals in XL are correct).
→ Add to TODO for future manual review and fix.
""")
