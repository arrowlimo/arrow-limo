#!/usr/bin/env python3
"""
Read vendor cleanup suggestions from Excel first column and apply to database.
"""

import psycopg2
import pandas as pd
import re

# Read the Excel file
excel_file = r"l:\limo\reports\all_vendors_20251221_151046.xlsx"
print("=" * 80)
print("READING VENDOR CLEANUP SUGGESTIONS")
print("=" * 80)
print(f"\nReading: {excel_file}")

df = pd.read_excel(excel_file, sheet_name='Receipt Vendors')
print(f"Loaded {len(df)} vendors")

# Check if there's a suggested revision column (first column)
print(f"\nColumns: {list(df.columns)}")
print("\nFirst 20 rows:")
print(df.head(20).to_string())

# Show any rows that have content in what might be a suggestion column
# (Looking for manually added column or notes)
if len(df.columns) > 6:
    print("\n\nExtra columns detected - showing rows with suggestions:")
    for idx, row in df.iterrows():
        if pd.notna(row.iloc[0]) and idx < 50:  # Show first 50 with suggestions
            print(f"\nRow {idx}:")
            for col_idx, val in enumerate(row):
                print(f"  Col {col_idx}: {val}")
