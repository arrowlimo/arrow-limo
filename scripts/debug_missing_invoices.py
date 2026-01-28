"""
Debug: Show raw rows from both sheets to find missing invoice data
"""
import pandas as pd

EXCEL_FILE = r"L:\limo\receipts\Document_20171129_0001.xlsx"

try:
    # Sheet 1
    df1 = pd.read_excel(EXCEL_FILE, sheet_name='Sheet1', header=None)
    print(f"SHEET 1: {len(df1)} rows")
    print("="*120)
    for idx, row in df1.iterrows():
        # Show rows that have date-like values
        if pd.notna(row.iloc[0]):
            try:
                date_val = pd.to_datetime(row.iloc[0], errors='coerce')
                if pd.notna(date_val):
                    desc = str(row.iloc[1]) if len(row) > 1 and pd.notna(row.iloc[1]) else ""
                    if 'INV' in desc:
                        print(f"Row {idx:2d}: Date={date_val.date()} | Desc={desc[:80]}")
            except:
                pass
    
    # Sheet 2
    df2 = pd.read_excel(EXCEL_FILE, sheet_name='Sheet2', header=None)
    print(f"\nSHEET 2: {len(df2)} rows")
    print("="*120)
    for idx, row in df2.iterrows():
        if pd.notna(row.iloc[0]):
            try:
                date_val = pd.to_datetime(row.iloc[0], errors='coerce')
                if pd.notna(date_val):
                    desc = str(row.iloc[1]) if len(row) > 1 and pd.notna(row.iloc[1]) else ""
                    if 'INV' in desc:
                        print(f"Row {idx:2d}: Date={date_val.date()} | Desc={desc[:80]}")
            except:
                pass

except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
