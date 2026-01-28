import pandas as pd

# Check 2012 QuickBooks register
df = pd.read_csv(r'l:\limo\exports\banking\2012_qb_register_parsed.csv')

print(f"Total rows: {len(df)}")
print(f"Date range: {df['date'].min()} to {df['date'].max()}")
print(f"Non-empty names: {df['name'].notna().sum()}")
print(f"Non-empty memos: {df['memo'].notna().sum()}")
print(f"\nFirst 10 rows:")
print(df.head(10).to_string())
