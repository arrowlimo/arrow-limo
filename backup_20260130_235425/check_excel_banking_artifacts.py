"""
Check Excel workbook for banking artifacts (#dd and X patterns)
"""
import pandas as pd

# Read Banking Transactions sheet
xl_path = r'L:\limo\reports\complete_receipts_workbook_20251205_162410.xlsx'
df = pd.read_excel(xl_path, sheet_name='Banking Transactions')

print("=== Banking Artifacts in Excel Report ===\n")

# Search for #dd patterns
artifacts_dd = df[df['Description'].str.contains('#dd', case=False, na=False)]
print(f"#dd patterns found: {len(artifacts_dd)}\n")
if len(artifacts_dd) > 0:
    print(artifacts_dd[['Transaction ID', 'Description', 'Vendor Extracted']].head(10))
    print()

# Search for descriptions ending with space X
artifacts_x = df[df['Description'].str.contains(r'\sX$', regex=True, na=False)]
print(f"\nDescriptions ending with ' X': {len(artifacts_x)}\n")
if len(artifacts_x) > 0:
    print(artifacts_x[['Transaction ID', 'Description', 'Vendor Extracted']].head(10))
    print()

# Also check for the specific example mentioned: "Cheque #dd Hertz X"
hertz_artifacts = df[df['Description'].str.contains('Hertz', case=False, na=False)]
print(f"\nAll Hertz transactions: {len(hertz_artifacts)}\n")
if len(hertz_artifacts) > 0:
    print(hertz_artifacts[['Transaction ID', 'Description', 'Vendor Extracted']])
