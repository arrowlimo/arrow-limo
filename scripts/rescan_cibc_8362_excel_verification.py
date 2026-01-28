"""
Re-scan CIBC 8362 2014-2017 Excel file to verify corrections before import
"""
import pandas as pd
from datetime import datetime

file_path = r"L:\limo\CIBC UPLOADS\0228362 (CIBC checking account)\2014-2017 CIBC 8362.xlsx"

print("=" * 100)
print("RE-SCANNING CIBC 8362 (2014-2017) EXCEL FILE - VERIFICATION BEFORE RE-IMPORT")
print("=" * 100)

# Load Excel
df = pd.read_excel(file_path)

# Fix date typo
df['date'] = df['date'].astype(str).str.replace('/214', '/2014', regex=False)
df['date'] = pd.to_datetime(df['date'], errors='coerce')

print(f"\n✅ Loaded {len(df):,} rows")
print(f"Date range: {df['date'].min()} to {df['date'].max()}\n")

# Check for previous errors
print("=" * 100)
print("CHECKING FOR PREVIOUSLY IDENTIFIED ERRORS")
print("=" * 100)

# 1. Check SQUARE DEPOSIT in debit column
df['debit'] = pd.to_numeric(df['debit/withdrawal'], errors='coerce')
df['credit'] = pd.to_numeric(df['deposit/credit'], errors='coerce')

square_deposit_debit = df[
    (df['Description'].str.upper().str.contains('SQUARE DEPOSIT', na=False)) & 
    (df['debit'].notna()) & 
    (df['debit'] > 0)
]

print(f"\n1. SQUARE DEPOSIT in debit column (should be 0 if fixed):")
if len(square_deposit_debit) > 0:
    print(f"   ❌ STILL {len(square_deposit_debit)} ERRORS FOUND:\n")
    for idx, row in square_deposit_debit.iterrows():
        print(f"   {row['date'].date()} - ${row['debit']:.2f} - {row['Description']}")
else:
    print(f"   ✅ FIXED - No SQUARE DEPOSIT in debit column")

# 2. Check for STOPP typo
stopp_typo = df[df['Description'].str.contains('STOPP', case=False, na=False)]

print(f"\n2. STOPP typo check:")
if len(stopp_typo) > 0:
    print(f"   ❌ STILL {len(stopp_typo)} TYPOS FOUND:\n")
    for idx, row in stopp_typo.iterrows():
        print(f"   {row['date'].date()} - {row['Description']}")
else:
    print(f"   ✅ FIXED - No STOPP typos")

# 3. Check BANK WITHDRAWAL in credit (should be BANK DEPOSIT)
bank_withdrawal_credit = df[
    (df['Description'].str.upper().str.contains('BANK WITHDRAWAL', na=False)) & 
    (df['Description'].str.upper().str.contains('STOP', na=False) == False) &
    (df['credit'].notna()) & 
    (df['credit'] > 0)
]

print(f"\n3. BANK WITHDRAWAL in credit column (should be 0 if fixed):")
if len(bank_withdrawal_credit) > 0:
    print(f"   ❌ STILL {len(bank_withdrawal_credit)} ERRORS FOUND:\n")
    for idx, row in bank_withdrawal_credit.iterrows():
        print(f"   {row['date'].date()} - ${row['credit']:.2f} - {row['Description']}")
else:
    print(f"   ✅ FIXED - No BANK WITHDRAWAL in credit column")

# 4. Check BANK DEPOSIT in debit (should be BANK FEE or other)
bank_deposit_debit = df[
    (df['Description'].str.upper().str.contains('BANK DEPOSIT', na=False)) & 
    (df['Description'].str.upper().str.contains('STOP', na=False) == False) &
    (df['debit'].notna()) & 
    (df['debit'] > 0)
]

print(f"\n4. BANK DEPOSIT in debit column (should be 0 if fixed):")
if len(bank_deposit_debit) > 0:
    print(f"   ❌ STILL {len(bank_deposit_debit)} ERRORS FOUND:\n")
    for idx, row in bank_deposit_debit.iterrows():
        print(f"   {row['date'].date()} - ${row['debit']:.2f} - {row['Description']}")
else:
    print(f"   ✅ FIXED - No BANK DEPOSIT in debit column")

# 5. Verify specific corrections were made
print(f"\n5. Checking specific corrections:")

# WOK BOX (was SQUARE DEPOSIT on 2014-10-23)
wok_box = df[
    (df['date'].dt.date == datetime(2014, 10, 23).date()) & 
    (df['Description'].str.upper().str.contains('WOK', na=False))
]
if len(wok_box) > 0:
    print(f"   ✅ WOK BOX found on 2014-10-23: {wok_box.iloc[0]['Description']}")
else:
    print(f"   ⚠️ WOK BOX not found on 2014-10-23 (check if still SQUARE DEPOSIT)")

# SQUARE FEE (should have replaced many SQUARE DEPOSIT)
square_fee = df[df['Description'].str.upper().str.contains('SQUARE FEE', na=False)]
print(f"   SQUARE FEE count: {len(square_fee)} (should be ~13 if all fixed)")

# Summary
print("\n" + "=" * 100)
print("VERIFICATION SUMMARY")
print("=" * 100)

total_errors = len(square_deposit_debit) + len(stopp_typo) + len(bank_withdrawal_credit) + len(bank_deposit_debit)

if total_errors == 0:
    print("✅ ALL ERRORS FIXED - File is ready for import!")
    print(f"   - Total rows: {len(df):,}")
    print(f"   - Date range: {df['date'].min().date()} to {df['date'].max().date()}")
else:
    print(f"❌ {total_errors} ERRORS STILL REMAIN - DO NOT IMPORT YET")
    print("\nFix these errors in Excel and re-run this scan.")

print("\n" + "=" * 100)
