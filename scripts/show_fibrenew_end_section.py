#!/usr/bin/env python3
"""
Show the complete end section of Fibrenew Excel file to find 2025 balance data.
"""

import pandas as pd
from datetime import datetime

EXCEL_FILE = r'L:\limo\pdf\2012\fibrenew.xlsx'

# Read Excel file
df = pd.read_excel(EXCEL_FILE, header=None)

print("="*80)
print("FIBRENEW EXCEL - LAST 30 ROWS")
print("="*80)

for idx in range(max(0, len(df) - 30), len(df)):
    row = df.iloc[idx]
    col0 = str(row[0]) if not pd.isna(row[0]) else ''
    col1 = str(row[1]) if not pd.isna(row[1]) else ''
    col2 = str(row[2]) if not pd.isna(row[2]) else ''
    col3 = str(row[3]) if not pd.isna(row[3]) else '' if len(row) > 3 else ''
    
    print(f"Row {idx:3d}: {col0:20s} | {col1:25s} | {col2:15s} | {col3}")

print("\n" + "="*80)
print("SEARCHING FOR 2016+ DATA AND BALANCE NOTES")
print("="*80)

for idx, row in df.iterrows():
    col0 = str(row[0]).strip() if not pd.isna(row[0]) else ''
    col1 = str(row[1]).strip() if not pd.isna(row[1]) else ''
    col2 = str(row[2]).strip() if not pd.isna(row[2]) else ''
    col3 = str(row[3]).strip() if not pd.isna(row[3]) else '' if len(row) > 3 else ''
    
    # Look for 2016+ years in any column
    if any(y in text for y in ['2016', '2017', '2018', '2019', '2020', '2021', '2022', '2023', '2024', '2025'] 
           for text in [col0, col1, col2, col3]):
        print(f"Row {idx}: {col0:15s} | {col1:20s} | {col2:15s} | {col3}")
    
    # Look for balance/owing keywords
    if any(kw in text.lower() for kw in ['balance', 'owing', 'owe', 'outstanding', 'unpaid', '14000', '14,000']
           for text in [col0, col1, col2, col3]):
        print(f"Row {idx}: {col0:15s} | {col1:20s} | {col2:15s} | {col3}")
