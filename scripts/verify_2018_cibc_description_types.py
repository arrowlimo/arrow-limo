#!/usr/bin/env python3
"""Verify that CIBC 2018 transaction descriptions match actual debit/credit columns."""

import pandas as pd
import numpy as np

# Read the Excel file
df = pd.read_excel(r'L:\limo\CIBC UPLOADS\0228362 (CIBC checking account)\2018 CIBC 8362.xlsx')

print(f"Total transactions: {len(df)}")
print(f"Date range: {df['date'].min()} to {df['date'].max()}\n")

# Check for mismatches
print("=" * 80)
print("CHECKING FOR DESCRIPTION vs ACTUAL TYPE MISMATCHES")
print("=" * 80)

# Look for "WITHDRAWAL" in description
withdrawal_desc = df[df['Description'].str.contains('WITHDRAWAL', case=False, na=False)]
print(f"\n1. Transactions with 'WITHDRAWAL' in description: {len(withdrawal_desc)}")

# Check if any are actually deposits (have deposit/credit value)
withdrawal_but_deposit = withdrawal_desc[withdrawal_desc['deposit/credit'].notna()]
if len(withdrawal_but_deposit) > 0:
    print(f"   ⚠️  WARNING: {len(withdrawal_but_deposit)} have 'WITHDRAWAL' but are in deposit/credit column!")
    print("\n   Details:")
    for idx, row in withdrawal_but_deposit.iterrows():
        print(f"   Row {idx}: {row['date']} | {row['Description'][:50]:50s} | DEPOSIT: ${row['deposit/credit']:,.2f}")
else:
    print(f"   ✅ All {len(withdrawal_desc)} match correctly (in debit/withdrawal column)")

# Look for "DEPOSIT" in description
deposit_desc = df[df['Description'].str.contains('DEPOSIT', case=False, na=False)]
print(f"\n2. Transactions with 'DEPOSIT' in description: {len(deposit_desc)}")

# Check if any are actually withdrawals (have debit/withdrawal value)
deposit_but_withdrawal = deposit_desc[deposit_desc['debit/withdrawal'].notna()]
if len(deposit_but_withdrawal) > 0:
    print(f"   ⚠️  WARNING: {len(deposit_but_withdrawal)} have 'DEPOSIT' but are in debit/withdrawal column!")
    print("\n   Details:")
    for idx, row in deposit_but_withdrawal.iterrows():
        print(f"   Row {idx}: {row['date']} | {row['Description'][:50]:50s} | DEBIT: ${row['debit/withdrawal']:,.2f}")
else:
    print(f"   ✅ All {len(deposit_desc)} match correctly (in deposit/credit column)")

# Look for other common keywords
print("\n" + "=" * 80)
print("OTHER KEYWORD CHECKS")
print("=" * 80)

keywords = ['TRANSFER', 'PAYMENT', 'ATM', 'CASH', 'CHECK', 'CHEQUE']
for keyword in keywords:
    matches = df[df['Description'].str.contains(keyword, case=False, na=False)]
    if len(matches) > 0:
        deposits = matches[matches['deposit/credit'].notna()]
        debits = matches[matches['debit/withdrawal'].notna()]
        print(f"\n'{keyword}': {len(matches)} total ({len(deposits)} deposits, {len(debits)} debits)")

# Show all BANK WITHDRAWAL transactions
print("\n" + "=" * 80)
print("ALL 'BANK WITHDRAWAL' TRANSACTIONS")
print("=" * 80)

bank_withdrawals = df[df['Description'].str.contains('BANK WITHDRAWAL', case=False, na=False)]
print(f"\nFound {len(bank_withdrawals)} transactions:")
print(f"\nDebit column (withdrawals): {len(bank_withdrawals[bank_withdrawals['debit/withdrawal'].notna()])}")
print(f"Credit column (deposits): {len(bank_withdrawals[bank_withdrawals['deposit/credit'].notna()])}")

if len(bank_withdrawals[bank_withdrawals['deposit/credit'].notna()]) > 0:
    print("\n⚠️  BANK WITHDRAWALS THAT ARE ACTUALLY DEPOSITS:")
    for idx, row in bank_withdrawals[bank_withdrawals['deposit/credit'].notna()].iterrows():
        print(f"  {row['date']} | Deposit: ${row['deposit/credit']:,.2f} | Balance: ${row['balance']:,.2f}")

# Sample of bank withdrawals as debits
print("\nSample BANK WITHDRAWALS as debits (first 5):")
debit_withdrawals = bank_withdrawals[bank_withdrawals['debit/withdrawal'].notna()].head(5)
for idx, row in debit_withdrawals.iterrows():
    print(f"  {row['date']} | Debit: ${row['debit/withdrawal']:,.2f} | Balance: ${row['balance']:,.2f}")
