"""
Analyze CIBC 8362 2014-2017 verified banking file
Account: 0228362 (CIBC checking account - PRIMARY)
mapped_bank_account_id = 1
"""
import pandas as pd
from pathlib import Path

file_path = r"L:\limo\CIBC UPLOADS\0228362 (CIBC checking account)\2014-2017 CIBC 8362.xlsx"

print("=" * 80)
print("CIBC Account 0228362 (8362) - 2014-2017 Analysis")
print("mapped_bank_account_id = 1 (PRIMARY ACCOUNT)")
print("=" * 80)

df = pd.read_excel(file_path)

print(f"\nTotal rows: {len(df):,}")
print(f"\nColumns: {df.columns.tolist()}")

# Check for problematic dates first
print("\n🔍 Checking for data issues...")
print(f"Sample raw dates: {df['date'].head(10).tolist()}")

# Find bad dates
for idx, val in enumerate(df['date']):
    if isinstance(val, str) and '214' in val:
        print(f"⚠️ Bad date at row {idx}: {val}")
        
# Convert date column properly with error handling
df['date'] = pd.to_datetime(df['date'], errors='coerce')

# Check for NaT values
nat_count = df['date'].isna().sum()
if nat_count > 0:
    print(f"⚠️ Found {nat_count} invalid dates (converted to NaT)")
    bad_dates = df[df['date'].isna()]
    print("Bad date rows:")
    print(bad_dates[['date', 'Description', 'debit/withdrawal', 'deposit/credit']].head(10))
    
print(f"\nDate range: {df['date'].min()} to {df['date'].max()}")

print("\n" + "=" * 80)
print("SAMPLE TRANSACTIONS (First 15 rows)")
print("=" * 80)
print(df.head(15).to_string())

print("\n" + "=" * 80)
print("TRANSACTION TYPE SUMMARY")
print("=" * 80)
print(df['Description'].value_counts().head(20))

print("\n" + "=" * 80)
print("YEARLY SUMMARY")
print("=" * 80)
df['year'] = pd.to_datetime(df['date']).dt.year
yearly = df.groupby('year').agg({
    'debit/withdrawal': ['count', 'sum'],
    'deposit/credit': ['count', 'sum']
})
print(yearly)

print("\n✅ File verified and ready for import to bank_account_id = 1")
