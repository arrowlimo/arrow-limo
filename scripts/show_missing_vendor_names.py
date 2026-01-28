#!/usr/bin/env python3
"""
Show which cheques in vendor reference XLS still need vendor names
Helps prioritize which ones to fill in next
"""
import pandas as pd
import sys

def main():
    xls_path = "l:/limo/reports/cheque_vendor_reference.xlsx"
    
    print("="*80)
    print("VENDOR REFERENCE XLS - MISSING VENDOR NAMES")
    print("="*80)
    
    xls = pd.ExcelFile(xls_path)
    
    pd.set_option('display.max_columns', None)
    pd.set_option('display.width', 200)
    
    for sheet in xls.sheet_names:
        if sheet == 'Summary':
            continue
        
        print(f"\n{'='*80}")
        print(f"SHEET: {sheet}")
        print(f"{'='*80}")
        
        df = pd.read_excel(xls, sheet_name=sheet)
        
        chq_col = 'CHQ #' if 'CHQ #' in df.columns else 'Cheque #'
        vendor_col = 'Vendor Name (ENTER HERE)'
        
        # Find rows without vendor names
        missing_vendor = df[vendor_col].isna() | (df[vendor_col].astype(str).str.strip() == '')
        
        total = len(df)
        completed = (~missing_vendor).sum()
        remaining = missing_vendor.sum()
        
        pct_complete = (completed / total * 100) if total > 0 else 0
        
        print(f"\nProgress: {completed}/{total} ({pct_complete:.1f}%) complete")
        print(f"Remaining to fill: {remaining}")
        
        if remaining > 0:
            print(f"\n{'='*80}")
            print("TOP 20 MISSING VENDOR NAMES (by amount - highest first)")
            print(f"{'='*80}")
            
            missing_df = df[missing_vendor].copy()
            # Convert Amount to numeric, handling any non-numeric values
            missing_df['Amount'] = pd.to_numeric(missing_df['Amount'], errors='coerce')
            missing_df = missing_df.dropna(subset=['Amount'])
            missing_df = missing_df.sort_values('Amount', ascending=False).head(20)
            
            for idx, row in missing_df.iterrows():
                cheque = row[chq_col]
                if pd.notna(cheque):
                    tx_id_val = f"{row['TX ID']:.0f}" if pd.notna(row['TX ID']) else 'N/A'
                    print(f"\nCheque #{cheque:.0f} | Date: {row['Date']} | Amount: ${row['Amount']:.2f}")
                    print(f"  Current: {row['Current Description']}")
                    print(f"  TX ID: {tx_id_val}")
            
            # Group by amount ranges
            print(f"\n{'='*80}")
            print("MISSING VENDORS BY AMOUNT RANGE")
            print(f"{'='*80}")
            
            ranges = [
                (5000, float('inf'), '$5,000+'),
                (1000, 5000, '$1,000 - $5,000'),
                (500, 1000, '$500 - $1,000'),
                (100, 500, '$100 - $500'),
                (0, 100, 'Under $100')
            ]
            
            for min_amt, max_amt, label in ranges:
                count = ((missing_df['Amount'] >= min_amt) & (missing_df['Amount'] < max_amt)).sum()
                if count > 0:
                    total_amt = missing_df[(missing_df['Amount'] >= min_amt) & 
                                          (missing_df['Amount'] < max_amt)]['Amount'].sum()
                    print(f"  {label:20s}: {count:3d} cheques (${total_amt:,.2f})")

if __name__ == "__main__":
    main()
