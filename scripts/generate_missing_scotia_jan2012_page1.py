#!/usr/bin/env python3
"""
Generate missing_banking_rows CSV for Scotia Bank January 2012 Page 1
"""
import csv

screenshot_file = 'l:/limo/reports/screenshot_rows_scotia_jan2012_page1.csv'
missing_file = 'l:/limo/reports/missing_banking_rows_scotia_jan2012_page1.csv'

rows_to_add = []

with open(screenshot_file, 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        rows_to_add.append({
            'account_number': row['account_number'],
            'transaction_date': row['date'],
            'amount': row['amount'],
            'side': row['side'],
            'description': row['description'],
            'notes': 'Added from Scotia Bank Jan 2012 page 1',
            'source': 'scotia_screenshot'
        })

with open(missing_file, 'w', newline='', encoding='utf-8') as f:
    fieldnames = ['account_number', 'transaction_date', 'amount', 'side', 'description', 'notes', 'source']
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows_to_add)

print(f"[OK] Created {missing_file} with {len(rows_to_add)} rows")
