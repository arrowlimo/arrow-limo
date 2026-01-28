"""
More thorough extraction from Fibrenew statement Excel
Include ALL rows that might contain invoice data
"""
import pandas as pd
import re

EXCEL_FILE = r"L:\limo\receipts\Document_20171129_0001.xlsx"

try:
    # Read all sheets
    xl_file = pd.ExcelFile(EXCEL_FILE)
    print(f"Sheet names: {xl_file.sheet_names}")
    
    for sheet_name in xl_file.sheet_names:
        print(f"\n{'='*120}")
        print(f"SHEET: {sheet_name}")
        print(f"{'='*120}")
        
        df = pd.read_excel(EXCEL_FILE, sheet_name=sheet_name, header=None)
        print(f"Shape: {df.shape} (rows x columns)")
        
        # Display ALL rows to see complete data
        print("\nALL ROWS:")
        print("-"*120)
        for idx, row in df.iterrows():
            # Show non-empty cells
            non_empty = []
            for col_idx, val in enumerate(row):
                if pd.notna(val) and str(val).strip():
                    non_empty.append(f"Col{col_idx}={val}")
            if non_empty:
                print(f"Row {idx:3d}: {' | '.join(non_empty)}")
        
        # Look for the statement total
        print(f"\n{'='*120}")
        print("SEARCHING FOR TOTALS:")
        print("-"*120)
        for idx, row in df.iterrows():
            row_text = ' '.join([str(v) for v in row if pd.notna(v)])
            if 'total' in row_text.lower() or 'amount due' in row_text.lower() or '16,119' in row_text or '16119' in row_text:
                print(f"Row {idx}: {row_text}")

except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
