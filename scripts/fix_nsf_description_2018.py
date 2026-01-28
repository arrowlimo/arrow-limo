#!/usr/bin/env python3
"""Fix NSF transaction description to match the reversal."""

import pandas as pd
import shutil
from datetime import datetime

# Backup the original file
original_file = r'L:\limo\CIBC UPLOADS\0228362 (CIBC checking account)\2018 CIBC 8362.xlsx'
backup_file = r'L:\limo\CIBC UPLOADS\0228362 (CIBC checking account)\2018 CIBC 8362_backup_before_nsf_fix.xlsx'

shutil.copy2(original_file, backup_file)
print(f"✅ Backed up original to: {backup_file}\n")

# Read the Excel file
df = pd.read_excel(original_file)

print("BEFORE FIX:")
print("=" * 80)
jan3_rows = df[(df['date'] >= '2018-01-03') & (df['date'] <= '2018-01-04')]
print(jan3_rows[['date', 'Description', 'debit/withdrawal', 'deposit/credit', 'balance']].to_string())

# Fix row 22: Change "ASI FINANCE" to "NSF RETURN ASI FINANCE"
# This is the debit that should match the credit reversal
df.loc[22, 'Description'] = 'NSF RETURN ASI FINANCE'

print("\n\nAFTER FIX:")
print("=" * 80)
jan3_rows = df[(df['date'] >= '2018-01-03') & (df['date'] <= '2018-01-04')]
print(jan3_rows[['date', 'Description', 'debit/withdrawal', 'deposit/credit', 'balance']].to_string())

# Save the updated file
df.to_excel(original_file, index=False)
print(f"\n✅ Updated file saved: {original_file}")
print(f"\n✅ NSF transactions now have matching descriptions")
