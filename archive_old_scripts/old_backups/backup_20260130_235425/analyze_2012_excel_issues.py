#!/usr/bin/env python3
"""Analyze 2012 reconciliation Excel for duplicates and NSF issues."""

import pandas as pd
import sys

excel_file = r'L:\limo\2012_Banking_Receipts_Reconciliation_20251204_221051.xlsx'

print('='*70)
print('ANALYZING RECEIPTS SHEET FOR DUPLICATES')
print('='*70)
print()

df = pd.read_excel(excel_file, sheet_name='Receipts 2012')
print(f'Total rows in Receipts sheet: {len(df):,}')
print()

# Check for exact duplicates (all fields)
exact_dupes = df.duplicated(keep=False).sum()
print(f'Exact duplicate rows: {exact_dupes:,} ({exact_dupes/len(df)*100:.1f}%)')

# Check for duplicate receipts based on date + vendor + amount
duplicate_mask = df.duplicated(subset=['Date', 'Vendor', 'Gross Amount'], keep=False)
duplicate_count = duplicate_mask.sum()
print(f'Duplicate receipts (by date+vendor+amount): {duplicate_count:,} ({duplicate_count/len(df)*100:.1f}%)')

if duplicate_count > 0:
    print()
    print('Analyzing duplicate groups...')
    
    # Group by date+vendor+amount and count occurrences
    dupe_groups = df[duplicate_mask].groupby(['Date', 'Vendor', 'Gross Amount']).size().reset_index(name='count')
    dupe_groups = dupe_groups.sort_values('count', ascending=False)
    
    print(f'\nDuplicate groups by frequency:')
    print(f'  2x duplicates: {len(dupe_groups[dupe_groups["count"] == 2]):,} groups')
    print(f'  3x duplicates: {len(dupe_groups[dupe_groups["count"] == 3]):,} groups')
    print(f'  4x duplicates: {len(dupe_groups[dupe_groups["count"] == 4]):,} groups')
    print(f'  5x+ duplicates: {len(dupe_groups[dupe_groups["count"] >= 5]):,} groups')
    
    print()
    print('Top 10 worst duplicate groups:')
    for idx, row in dupe_groups.head(10).iterrows():
        date = row['Date']
        vendor = row['Vendor']
        amount = row['Gross Amount']
        count = row['count']
        print(f'  {date} | {vendor[:30]:30} | ${amount:,.2f} | {count}x copies')

print()
print('='*70)
print('CHECKING NSF TRANSACTION HANDLING')
print('='*70)
print()

# Check NSF-related receipts
nsf_mask = df['Description'].astype(str).str.contains('NSF|nsf', case=False, na=False)
nsf_receipts = df[nsf_mask]
print(f'Total NSF-related receipts: {len(nsf_receipts)}')
print()

if len(nsf_receipts) > 0:
    print('NSF transactions (showing amount signs):')
    nsf_display = nsf_receipts[['Date', 'Vendor', 'Gross Amount', 'Category', 'Description']].copy()
    for idx, row in nsf_display.iterrows():
        date = row['Date']
        vendor = row['Vendor']
        amount = row['Gross Amount']
        category = row['Category']
        desc = row['Description']
        sign = '+' if amount > 0 else '-'
        print(f'{date} | {vendor[:20]:20} | {sign}${abs(amount):9,.2f} | {category:15} | {desc[:40]}')
    
    print()
    print('ISSUE: NSF charges and reversals should cancel out:')
    print('  - NSF CHARGE (bank fee): Should be POSITIVE (withdrawal/expense)')
    print('  - NSF REVERSAL (bounced payment reversed): Should be NEGATIVE (deposit/income reversal)')
    print('  - Currently both appear as POSITIVE, so they double instead of cancelling')

print()
print('='*70)
print('SUMMARY')
print('='*70)
print(f'Total receipts: {len(df):,}')
print(f'Duplicates to remove: {duplicate_count:,} ({duplicate_count/len(df)*100:.1f}%)')
print(f'NSF transactions needing sign correction: {len(nsf_receipts)}')
print()
print('RECOMMENDED ACTIONS:')
print('  1. Remove duplicate receipts (keep only one copy of each)')
print('  2. Fix NSF transaction signs (reversals should be negative)')
print('  3. Regenerate Excel file with corrected data')
