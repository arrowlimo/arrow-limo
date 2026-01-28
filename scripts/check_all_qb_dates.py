#!/usr/bin/env python
"""
Check date ranges in all QB files
"""
import pandas as pd
from pathlib import Path

base = Path("L:/limo/quickbooks/old quickbooks")

files = [
    "initial journal.xlsx",
    "initial adjusted journal entreis.xlsx",
    "initial check details.xlsx",
    "initial deposts.xlsx",
    "initial tax agency detail report.xlsx",
    "initial transaction details.xlsx"
]

print("DATE RANGES IN QUICKBOOKS EXPORT FILES")
print("="*80)

for fname in files:
    filepath = base / fname
    if not filepath.exists():
        print(f"\n{fname}: FILE NOT FOUND")
        continue
    
    try:
        df = pd.read_excel(filepath, header=3)
        df = df[df['Date'].notna()]
        
        if len(df) > 0:
            df['Date'] = pd.to_datetime(df['Date'])
            min_date = df['Date'].min()
            max_date = df['Date'].max()
            count = len(df)
            
            before_2012 = len(df[df['Date'] < '2012-01-01'])
            
            print(f"\n{fname}:")
            print(f"  Total rows with dates: {count:,}")
            print(f"  Date range: {min_date.date()} to {max_date.date()}")
            print(f"  Rows before 2012: {before_2012:,}")
            print(f"  Rows 2012+: {count - before_2012:,}")
        else:
            print(f"\n{fname}: NO DATE COLUMN FOUND")
    except Exception as e:
        print(f"\n{fname}: ERROR - {e}")

print("\n" + "="*80)
