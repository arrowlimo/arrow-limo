#!/usr/bin/env python3
"""Remove non-2012 rows (header/footer junk from 2015/2019)."""

import openpyxl
import pandas as pd
from datetime import datetime

xlsx_path = r"l:\limo\data\2012_scotia_transactions_for_editing.xlsx"

print("=" * 80)
print("CLEANING NON-2012 ROWS FROM SCOTIA FILE")
print("=" * 80)

# Load with pandas to identify bad rows
df = pd.read_excel(xlsx_path, sheet_name=0)
df['year'] = pd.to_datetime(df['date'], errors='coerce').dt.year

print(f"\nTotal rows before cleanup: {len(df)}")

# Count by year
year_counts = df['year'].value_counts().sort_index()
print(f"\nRows by year:")
for year, count in year_counts.items():
    if pd.notna(year):
        print(f"  {int(year)}: {count} rows")
    else:
        print(f"  (invalid date): {count} rows")

# Identify rows to keep (only 2012)
rows_to_keep = df[df['year'] == 2012]
rows_to_remove = df[df['year'] != 2012]

print(f"\n✓ Keeping {len(rows_to_keep)} rows from 2012")
print(f"✗ Removing {len(rows_to_remove)} rows from other years:")
for idx in rows_to_remove.index:
    row = df.iloc[idx]
    date_str = str(row['date'])[:10] if pd.notna(row['date']) else "MISSING"
    desc = str(row['Description'])[:30] if pd.notna(row['Description']) else "(empty)"
    print(f"  Row {idx + 2}: {date_str} | {desc}")

# Load workbook and remove bad rows
wb = openpyxl.load_workbook(xlsx_path)
ws = wb.active

# Delete rows in reverse order (from bottom up)
rows_deleted = []
for idx in sorted(rows_to_remove.index, reverse=True):
    excel_row = idx + 2  # +2 for header
    ws.delete_rows(excel_row)
    rows_deleted.append(excel_row)

print(f"\nDeleted {len(rows_deleted)} Excel rows: {sorted(rows_deleted)}")

# Save cleaned file
wb.save(xlsx_path)
print(f"\n✓ Saved cleaned file: {xlsx_path}")

# Verify
df_clean = pd.read_excel(xlsx_path, sheet_name=0)
print(f"\nVerification:")
print(f"  Total rows after cleanup: {len(df_clean)}")
print(f"  Date range: {df_clean['date'].min()} to {df_clean['date'].max()}")

print("\n" + "=" * 80)
print("✓ CLEANUP COMPLETE - All non-2012 rows removed")
print("=" * 80)

wb.close()
