#!/usr/bin/env python3
"""
Generate missing_banking_rows CSV from screenshot validation results
"""
import csv
import os

# Read the screenshot file
screenshot_file = 'l:/limo/reports/screenshot_rows_dec2012_page1.csv'
missing_file = 'l:/limo/reports/missing_banking_rows_dec2012_page1.csv'

# Account mapping: statement format -> canonical account number
ACCOUNT_MAP = {
    '00339-7461615': '0228362',  # Main CIBC operating account
}

rows_to_add = []

with open(screenshot_file, 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        stmt_acct = row['account_number']
        canonical_acct = ACCOUNT_MAP.get(stmt_acct, stmt_acct)
        date = row['date']
        amount = row['amount']
        side = row['side']
        desc = row['description']
        
        rows_to_add.append({
            'account_number': canonical_acct,
            'transaction_date': date,
            'amount': amount,
            'side': side,
            'description': desc,
            'notes': f'Added from CIBC Dec 2012 page 1',
            'source': 'cibc_screenshot'
        })

# Write missing rows file
with open(missing_file, 'w', newline='', encoding='utf-8') as f:
    fieldnames = ['account_number', 'transaction_date', 'amount', 'side', 'description', 'notes', 'source']
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows_to_add)

print(f"[OK] Created {missing_file} with {len(rows_to_add)} rows")
