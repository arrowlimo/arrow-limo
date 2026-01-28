#!/usr/bin/env python3
"""
Check for invalid dates in the verified Scotia 2013-2014 Excel file
"""

import pandas as pd

XLSX_FILE = "L:/limo/data/2013_scotia_transactions_for_editingfinal.xlsx"

print("="*80)
print("CHECKING INVALID DATES IN VERIFIED SCOTIA FILE")
print("="*80)

# Load file
df = pd.read_excel(XLSX_FILE, sheet_name=0)
print(f"\n✅ Loaded {len(df)} rows")

# Try to convert dates
df['date_parsed'] = pd.to_datetime(df['date'], errors='coerce')

# Find invalid dates
invalid = df[df['date_parsed'].isna()]

if len(invalid) > 0:
    print(f"\n❌ Found {len(invalid)} rows with invalid dates:")
    print("\nRow# | Original Date | Description | Debit | Credit | Balance")
    print("-" * 80)
    
    for idx, row in invalid.iterrows():
        desc = str(row['Description'])[:40] if pd.notna(row['Description']) else ''
        debit = f"${row['debit/withdrawal']:,.2f}" if pd.notna(row['debit/withdrawal']) else ''
        credit = f"${row['deposit/credit']:,.2f}" if pd.notna(row['deposit/credit']) else ''
        balance = f"${row['balance']:,.2f}" if pd.notna(row['balance']) else ''
        
        print(f"{idx:4d} | {str(row['date']):13s} | {desc:40s} | {debit:12s} | {credit:12s} | {balance:12s}")
else:
    print("\n✅ No invalid dates found - all dates parsed successfully")

print("\n" + "="*80)
