"""
Analyze Fibrenew invoice Excel file to extract invoice details
Shows original amounts vs amounts due (indicating partial payments)
"""
import pandas as pd
import sys

EXCEL_FILE = r"L:\limo\receipts\Document_20171129_0001.xlsx"

try:
    # Read all sheets
    xl = pd.ExcelFile(EXCEL_FILE)
    print(f"\nFile: {EXCEL_FILE}")
    print(f"Sheets: {xl.sheet_names}\n")
    
    for sheet_name in xl.sheet_names:
        print(f"\n{'='*100}")
        print(f"SHEET: {sheet_name}")
        print('='*100)
        
        df = pd.read_excel(EXCEL_FILE, sheet_name=sheet_name)
        print(f"Rows: {len(df)}, Columns: {len(df.columns)}")
        print(f"\nColumn names: {list(df.columns)}\n")
        
        # Show first 20 rows
        print(df.head(20).to_string(index=False))
        
        if len(df) > 20:
            print(f"\n... ({len(df) - 20} more rows)")
        
        # Look for key patterns
        print(f"\n\nKEY PATTERNS:")
        
        # Check for invoice numbers
        for col in df.columns:
            if 'invoice' in str(col).lower() or 'number' in str(col).lower():
                unique_vals = df[col].dropna().unique()
                if len(unique_vals) > 0 and len(unique_vals) < 50:
                    print(f"  {col}: {list(unique_vals[:10])}")
        
        # Check for amount columns
        for col in df.columns:
            if 'amount' in str(col).lower() or 'total' in str(col).lower() or 'due' in str(col).lower():
                print(f"  {col}: min=${df[col].min():.2f} max=${df[col].max():.2f} sum=${df[col].sum():.2f}")
        
        # Check for date columns
        for col in df.columns:
            if 'date' in str(col).lower():
                print(f"  {col}: {df[col].dropna().min()} to {df[col].dropna().max()}")

except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
