"""Debug Excel structure to understand actual data layout."""

import pandas as pd

# Test with one workbook
workbook = r"L:\limo\docs\2012-2013 excel\MASTER COPY 2012 YTD Hourly Payroll Workbook.xls1.xls"
sheet = "Jan.12"

print(f"Reading: {sheet}")
print("="*80)

df = pd.read_excel(workbook, sheet_name=sheet, header=None)

print(f"Total rows: {len(df)}")
print(f"Total columns: {len(df.columns)}")
print("\nAll rows (non-NaN values only):\n")

for idx in range(min(20, len(df))):
    row = df.iloc[idx]
    # Show only non-NaN values
    non_nan = [(i, val) for i, val in enumerate(row) if pd.notna(val)]
    if non_nan:
        print(f"Row {idx}:")
        for col_idx, val in non_nan:
            print(f"  Col {col_idx}: {val}")
        print()
