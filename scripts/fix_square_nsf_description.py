#!/usr/bin/env python3
"""Fix SQUARE DEPOSIT NSF to have proper description."""

import pandas as pd
import shutil

# Backup first
original_file = r'L:\limo\CIBC UPLOADS\0228362 (CIBC checking account)\2018 CIBC 8362.xlsx'
backup_file = r'L:\limo\CIBC UPLOADS\0228362 (CIBC checking account)\2018 CIBC 8362_backup_before_square_nsf_fix.xlsx'

shutil.copy2(original_file, backup_file)
print(f"✅ Backed up to: {backup_file}\n")

# Read file
df = pd.read_excel(original_file)

print("BEFORE FIX:")
print("=" * 80)
context = df.iloc[96:101]
print(context[['date', 'Description', 'debit/withdrawal', 'deposit/credit', 'balance']].to_string())

# Fix row 98: SQUARE DEPOSIT that's actually a debit (NSF)
df.loc[98, 'Description'] = 'NSF RETURN SQUARE DEPOSIT'

print("\n\nAFTER FIX:")
print("=" * 80)
context = df.iloc[96:101]
print(context[['date', 'Description', 'debit/withdrawal', 'deposit/credit', 'balance']].to_string())

# Save
df.to_excel(original_file, index=False)
print(f"\n✅ Updated: {original_file}")
print(f"✅ Row 98 description changed to 'NSF RETURN SQUARE DEPOSIT'")
