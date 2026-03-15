"""
Analyze the receipts table layout Excel file to understand the proper import structure.
"""

import pandas as pd
import openpyxl

# Read the Excel file
excel_file = r"L:\limo\reports\receipts table layout.xlsx"

print("=" * 80)
print("RECEIPTS TABLE LAYOUT ANALYSIS")
print("=" * 80)

# Try to read all sheets
xl_file = pd.ExcelFile(excel_file)
print(f"\nSheets in file: {xl_file.sheet_names}")

for sheet_name in xl_file.sheet_names:
    print(f"\n{'=' * 80}")
    print(f"SHEET: {sheet_name}")
    print("=" * 80)
    
    df = pd.read_excel(excel_file, sheet_name=sheet_name)
    
    print(f"\nShape: {df.shape[0]} rows x {df.shape[1]} columns")
    print(f"\nColumns: {list(df.columns)}")
    
    # Show first few rows
    print(f"\nFirst 10 rows:")
    print(df.head(10).to_string())
    
    # Check for any field mapping information
    if 'CSV Column' in df.columns or 'Database Column' in df.columns:
        print("\n*** FIELD MAPPING FOUND ***")
        print(df.to_string())

print("\n" + "=" * 80)
print("ANALYSIS COMPLETE")
print("=" * 80)
