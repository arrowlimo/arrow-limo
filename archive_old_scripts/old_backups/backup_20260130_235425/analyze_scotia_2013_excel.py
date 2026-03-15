import pandas as pd

# Check the Scotia 2013 Excel file structure
excel_path = r'l:\limo\pdf\2013\scotiabank JAN TO AUG 2013.xlsx'

# Get sheet names
xl = pd.ExcelFile(excel_path)
print(f"Sheet names: {xl.sheet_names}")
print(f"\nTotal sheets: {len(xl.sheet_names)}")

# Load first sheet to see structure
df = pd.read_excel(excel_path, sheet_name=0)
print(f"\nFirst sheet columns: {list(df.columns)}")
print(f"First sheet rows: {len(df)}")
print(f"\nFirst 10 rows:")
print(df.head(10).to_string())
