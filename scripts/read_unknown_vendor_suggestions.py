#!/usr/bin/env python3
"""
Read vendor cleanup suggestions from UNKNOWN_vendors Excel and apply to database.
"""

import psycopg2
import pandas as pd
import re

# Read the Excel file with user's suggested revisions
excel_file = r"l:\limo\reports\UNKNOWN_vendors_20251221_151046.xlsx"
print("=" * 80)
print("READING VENDOR CLEANUP SUGGESTIONS")
print("=" * 80)
print(f"\nReading: {excel_file}")

# Try to read the sheet with vendor data
try:
    df = pd.read_excel(excel_file, sheet_name='Receipt Vendors')
    print(f"Loaded Receipt Vendors sheet: {len(df)} rows")
except:
    print("Receipt Vendors sheet not found, trying first sheet...")
    df = pd.read_excel(excel_file, sheet_name=0)
    print(f"Loaded first sheet: {len(df)} rows")

print(f"\nColumns: {list(df.columns)}")

# Show first 30 rows to see the structure
print("\nFirst 30 rows:")
for idx in range(min(30, len(df))):
    row = df.iloc[idx]
    print(f"\nRow {idx}:")
    for col in df.columns:
        val = row[col]
        if pd.notna(val):
            print(f"  {col}: {val}")

# Look for rows where first column (suggested revision) is different from vendor name
print("\n" + "=" * 80)
print("SUGGESTED CHANGES")
print("=" * 80)

if len(df.columns) > 0:
    # Assume first column is suggested revision, second is current vendor name
    changes = []
    
    for idx, row in df.iterrows():
        # Check if there's a suggested revision (first column different from current)
        if len(row) >= 2:
            suggested = row.iloc[0]
            current = row.iloc[1] if len(row) > 1 else None
            
            if pd.notna(suggested) and pd.notna(current):
                if str(suggested).strip() != str(current).strip():
                    # Exclude comments in parentheses
                    if not str(suggested).strip().startswith('('):
                        changes.append({
                            'from': str(current).strip(),
                            'to': str(suggested).strip(),
                            'row': idx
                        })
    
    print(f"\nFound {len(changes)} suggested vendor name changes:")
    for change in changes[:50]:  # Show first 50
        print(f"  Row {change['row']:4}: '{change['from']}' → '{change['to']}'")
    
    if len(changes) > 50:
        print(f"  ... and {len(changes) - 50} more")
