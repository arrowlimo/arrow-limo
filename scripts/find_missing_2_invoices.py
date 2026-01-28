"""
Find the 2 missing invoices - check for September 2018 gap
"""
import pandas as pd
import re

EXCEL_FILE = r"L:\limo\receipts\Document_20171129_0001.xlsx"

df1 = pd.read_excel(EXCEL_FILE, sheet_name='Sheet1', header=None)
df2 = pd.read_excel(EXCEL_FILE, sheet_name='Sheet2', header=None)

print("Checking Sheet1 rows 15-30 (around Sep 2018 gap):")
print("="*120)
for idx in range(15, 31):
    if idx < len(df1):
        row = df1.iloc[idx]
        if pd.notna(row.iloc[0]):
            try:
                date_val = pd.to_datetime(row.iloc[0], errors='coerce')
                if pd.notna(date_val):
                    desc = str(row.iloc[1]) if len(row) > 1 and pd.notna(row.iloc[1]) else ""
                    # Show all amounts
                    amounts = [f"${float(row.iloc[i]):,.2f}" for i in range(2, min(8, len(row))) if pd.notna(row.iloc[i]) and isinstance(row.iloc[i], (int, float))]
                    print(f"Row {idx:2d}: {date_val.date()} | {desc[:60]:60s} | {' | '.join(amounts)}")
            except:
                pass

print("\nChecking Sheet2 rows 5-15:")
print("="*120)
for idx in range(5, 16):
    if idx < len(df2):
        row = df2.iloc[idx]
        if pd.notna(row.iloc[0]):
            try:
                date_val = pd.to_datetime(row.iloc[0], errors='coerce')
                if pd.notna(date_val):
                    desc = str(row.iloc[1]) if len(row) > 1 and pd.notna(row.iloc[1]) else ""
                    amounts = [f"${float(row.iloc[i]):,.2f}" for i in range(2, min(8, len(row))) if pd.notna(row.iloc[i]) and isinstance(row.iloc[i], (int, float))]
                    print(f"Row {idx:2d}: {date_val.date()} | {desc[:60]:60s} | {' | '.join(amounts)}")
            except:
                pass
