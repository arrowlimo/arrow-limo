#!/usr/bin/env python3
"""
Batch process multiple Scotia Bank screenshot files
"""
import csv
import subprocess
import sys

files_to_process = [
    'scotia_mar2012_page1',
    'scotia_may2012_page1', 
    'scotia_may2012_page2'
]

for file_id in files_to_process:
    print(f"\n{'='*80}")
    print(f"Processing {file_id}")
    print('='*80)
    
    screenshot_file = f'l:/limo/reports/screenshot_rows_{file_id}.csv'
    missing_file = f'l:/limo/reports/missing_banking_rows_{file_id}.csv'
    
    # Generate missing rows
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
                'notes': f'Added from Scotia Bank {file_id}',
                'source': 'scotia_screenshot'
            })
    
    with open(missing_file, 'w', newline='', encoding='utf-8') as f:
        fieldnames = ['account_number', 'transaction_date', 'amount', 'side', 'description', 'notes', 'source']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows_to_add)
    
    print(f"[OK] Created {missing_file} with {len(rows_to_add)} rows")
    
    # Apply missing rows
    print(f"\nInserting transactions...")
    result = subprocess.run([
        sys.executable,
        'scripts/apply_missing_banking_rows.py',
        '--csv', missing_file,
        '--write'
    ], capture_output=True, text=True)
    
    print(result.stdout)
    if result.returncode != 0:
        print(f"ERROR: {result.stderr}")
        break
    
    # Validate
    print(f"\nValidating...")
    result = subprocess.run([
        sys.executable,
        'scripts/validate_screenshot_rows.py',
        '--input', screenshot_file,
        '--default-accounts', '903990106011'
    ], capture_output=True, text=True)
    
    print(result.stdout)

print(f"\n{'='*80}")
print("BATCH PROCESSING COMPLETE")
print('='*80)
