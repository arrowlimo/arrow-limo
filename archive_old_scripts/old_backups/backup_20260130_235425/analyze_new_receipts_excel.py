#!/usr/bin/env python3
"""
Analyze the Excel file 'reports/new receipts fileoct.xlsx':
- List sheet names and column names
- Show sample rows
- Identify fuel extraction columns and description 'split/{total}' patterns
- Output a small CSV summary for mapping to vehicle_fuel_log

Usage:
  python scripts/analyze_new_receipts_excel.py
"""
import os
import re
import pandas as pd

XLSX_PATH = r"L:\limo\reports\new receipts fileoct.xlsx"
OUTPUT_SUMMARY = r"L:\limo\reports\new_receipts_excel_summary.csv"


def main():
    if not os.path.exists(XLSX_PATH):
        print(f"File not found: {XLSX_PATH}")
        return
    xl = pd.ExcelFile(XLSX_PATH)
    print('Sheets:', xl.sheet_names)
    all_rows = []
    for sheet in xl.sheet_names:
        df = xl.parse(sheet)
        # Standardize columns (string names)
        df.columns = [str(c).strip() for c in df.columns]
        # Take a small sample
        sample = df.head(10).copy()
        # Detect likely fields
        cols = set(c.lower() for c in sample.columns)
        fuel_cols = [c for c in sample.columns if re.search(r"fuel|gas|diesel|lit(re|er)|vehicle|unit|plate|odometer|km", str(c), re.I)]
        desc_col = next((c for c in sample.columns if re.search(r"desc|detail|memo|note", str(c), re.I)), None)
        amount_col = next((c for c in sample.columns if re.search(r"amount|total|gross|net|paid", str(c), re.I)), None)
        date_col = next((c for c in sample.columns if re.search(r"date", str(c), re.I)), None)
        # Scan split pattern
        split_info = []
        if desc_col:
            for val in sample[desc_col].astype(str).fillna(''):
                m = re.search(r"split\s*/\s*\$?([0-9,.]+)", val, re.I)
                if m:
                    split_info.append(m.group(1))
        # Collect rows for output
        for _, row in sample.iterrows():
            all_rows.append({
                'sheet': sheet,
                'date': row.get(date_col),
                'description': row.get(desc_col),
                'amount_col': amount_col,
                'amount': row.get(amount_col),
                'fuel_cols_detected': ';'.join(fuel_cols),
                'split_total_seen': ';'.join(split_info) if split_info else ''
            })
        print(f"\nSheet '{sheet}':")
        print('Columns:', list(df.columns))
        print('Likely date column:', date_col)
        print('Likely amount column:', amount_col)
        print('Likely description column:', desc_col)
        print('Fuel-related columns:', fuel_cols)
        if split_info:
            print('Found split totals in description:', split_info[:3])
    # Write summary CSV
    if all_rows:
        pd.DataFrame(all_rows).to_csv(OUTPUT_SUMMARY, index=False)
        print(f"\nWrote summary to {OUTPUT_SUMMARY}")


if __name__ == '__main__':
    main()
