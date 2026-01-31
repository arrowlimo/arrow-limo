#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Parse 2012 YTD Hourly Payroll Workbooks.
These workbooks have multiple sheets with varying structures.
"""
import pandas as pd
import os
from pathlib import Path

workbooks = [
    r'L:\limo\docs\2012-2013 excel\MASTER COPY 2012 YTD Hourly Payroll Workbook.xls',
    r'L:\limo\docs\2012-2013 excel\MASTER COPY 2012 YTD Hourly Payroll Workbook.xls1.xls',
    r'L:\limo\docs\2012-2013 excel\MASTER COPY 2012 YTD Hourly Payroll Workbook.xls1a.xls',
]

def analyze_workbook(path):
    """Analyze structure of one workbook."""
    print(f"\n{'='*100}")
    print(f"Workbook: {Path(path).name}")
    print(f"{'='*100}")
    
    if not os.path.exists(path):
        print(f"  [WARN]  File not found!")
        return
    
    try:
        # Get all sheet names
        xl_file = pd.ExcelFile(path)
        print(f"\nSheets: {len(xl_file.sheet_names)}")
        
        for sheet_name in xl_file.sheet_names:
            print(f"\n--- Sheet: {sheet_name} ---")
            
            try:
                # Read first few rows to understand structure
                df = pd.read_excel(path, sheet_name=sheet_name, nrows=20)
                
                print(f"  Dimensions: {df.shape[0]} rows × {df.shape[1]} columns")
                print(f"  Columns: {list(df.columns[:10])}")
                
                # Show first few rows
                print(f"\n  First 5 rows:")
                print(df.head(5).to_string(index=False, max_colwidth=20))
                
                # Check for numeric columns (likely payroll data)
                numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
                if numeric_cols:
                    print(f"\n  Numeric columns: {numeric_cols[:10]}")
                
            except Exception as e:
                print(f"  [WARN]  Error reading sheet: {str(e)[:100]}")
    
    except Exception as e:
        print(f"  [WARN]  Error opening workbook: {str(e)[:100]}")


def main():
    print("2012 YTD Hourly Payroll Workbook Analysis")
    print("=" * 100)
    
    for wb_path in workbooks:
        analyze_workbook(wb_path)
    
    print("\n" + "=" * 100)
    print("Analysis complete!")


if __name__ == '__main__':
    main()
