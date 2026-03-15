import pandas as pd

# Load QuickBooks 2013 register data
df = pd.read_csv(r'l:\limo\exports\banking\2013_qb_register_parsed.csv')

print(f"Columns: {list(df.columns)}")
print(f"\nTotal rows: {len(df)}")
print(f"\nFirst 10 rows:")
print(df.head(10).to_string())
print(f"\nDate range: {df['date'].min()} to {df['date'].max()}")
print(f"\nAccount breakdown:")
print(df['account'].value_counts())
print(f"\nRows with non-empty vendor names: {df['name'].notna().sum()}")
print(f"\nRows with non-empty memos: {df['memo'].notna().sum()}")
