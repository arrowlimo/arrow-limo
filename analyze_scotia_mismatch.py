import pandas as pd

# Load backup
backup_df = pd.read_csv('L:/limo/backups/critical_backup_20251210_123930/scotia_2012_receipts_20251210_123930.csv')
print(f"BACKUP: {len(backup_df)} Scotia 2012 receipts were deleted")
print(f"\nColumns: {list(backup_df.columns)}")
print(f"\nPayment method breakdown:")
if 'payment_method' in backup_df.columns:
    print(backup_df['payment_method'].value_counts())
else:
    print("No payment_method column")

print(f"\n\nFirst 10 records:")
print(backup_df.head(10))

# Load Excel file
xlsx_df = pd.read_excel('L:/limo/data/2012_scotia_transactions_for_editing.xlsx')
print(f"\n\nEXCEL FILE: {len(xlsx_df)} records to import")
print(f"Columns: {list(xlsx_df.columns)}")
print(f"\nFirst 5 records:")
print(xlsx_df.head())
