"""
Examine the structure of multiinvoice.xls to understand the data layout
"""
import pandas as pd

print("="*80)
print("EXAMINING MULTIINVOICE.XLS STRUCTURE")
print("="*80)

# Read the Excel file
df = pd.read_excel(r'Z:\multiinvoice.xls', engine='xlrd')

print(f"\n📊 Shape: {df.shape} (rows, columns)")
print(f"📋 Columns: {list(df.columns)}\n")

# Find rows with "Perron Ventures" 
perron_mask = df.apply(lambda row: row.astype(str).str.contains('Perron Ventures', case=False, na=False).any(), axis=1)
perron_indices = df[perron_mask].index.tolist()

print(f"🔍 Found 'Perron Ventures' at row indices: {perron_indices[:10]}...")
print()

# Show a few sample rows with Perron Ventures
print("="*80)
print("SAMPLE PERRON VENTURES ROWS (showing all columns):")
print("="*80)

for idx in perron_indices[:3]:
    print(f"\nRow {idx}:")
    row = df.iloc[idx]
    for col_idx, col_name in enumerate(df.columns):
        val = row[col_name]
        if pd.notna(val) and str(val).strip() != '':
            print(f"  Col {col_idx:2d} ({col_name:30s}): {val}")

# Look for numeric patterns
print("\n" + "="*80)
print("SEARCHING FOR CHARTER NUMBERS (6-digit patterns):")
print("="*80)

import re
charter_pattern = re.compile(r'\b00[0-9]{4}\b')

for idx in perron_indices[:10]:
    row = df.iloc[idx]
    charter_nums = []
    amounts = []
    
    for col_idx, val in enumerate(row):
        val_str = str(val)
        # Look for charter numbers
        if charter_pattern.search(val_str):
            charter_nums.append((col_idx, val))
        # Look for amounts (numbers > 100)
        try:
            num = float(val)
            if 100 < num < 10000:
                amounts.append((col_idx, num))
        except:
            pass
    
    if charter_nums:
        print(f"\nRow {idx}:")
        print(f"  Charter numbers: {charter_nums}")
        print(f"  Amounts found: {amounts}")
