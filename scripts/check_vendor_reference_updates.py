#!/usr/bin/env python3
"""
Check vendor reference XLS for updates and prepare database sync
"""
import pandas as pd
import sys

def main():
    xls_path = "l:/limo/reports/cheque_vendor_reference.xlsx"
    
    print(f"Reading {xls_path}...")
    df = pd.read_excel(xls_path)
    
    print(f"\nTotal rows: {len(df)}")
    print(f"\nColumns: {list(df.columns)}")
    
    print("\n" + "="*80)
    print("FIRST 15 ROWS")
    print("="*80)
    pd.set_option('display.max_columns', None)
    pd.set_option('display.width', 200)
    print(df.head(15).to_string(index=False))
    
    # Look for status-related columns
    status_cols = [c for c in df.columns if any(x in c.lower() for x in 
                   ['status', 'void', 'nsf', 'clear', 'donat', 'loan', 'karen', 'note', 'comment'])]
    
    print(f"\n\nStatus-related columns found: {status_cols}")
    
    if status_cols:
        print("\n" + "="*80)
        print("ALL ROWS WITH STATUS INFO")
        print("="*80)
        display_cols = ['cheque_number', 'vendor', 'amount', 'payment_date'] + status_cols
        display_cols = [c for c in display_cols if c in df.columns]
        
        for idx, row in df.iterrows():
            has_status = any(pd.notna(row[c]) and str(row[c]).strip() != '' for c in status_cols if c in row.index)
            if has_status:
                print(f"\nRow {idx + 1}:")
                for col in display_cols:
                    if col in row.index:
                        val = row[col]
                        if pd.notna(val):
                            print(f"  {col}: {val}")
    
    # Summary statistics
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    
    for col in status_cols:
        if col in df.columns:
            non_empty = df[col].notna() & (df[col].astype(str).str.strip() != '')
            count = non_empty.sum()
            if count > 0:
                print(f"\n{col}: {count} entries")
                unique_vals = df.loc[non_empty, col].unique()
                for val in unique_vals:
                    val_count = (df[col] == val).sum()
                    print(f"  - {val}: {val_count}")

if __name__ == "__main__":
    main()
