#!/usr/bin/env python3
"""
Check QuickBooks data structure and account names.
"""

import csv
import os
from collections import Counter

def main():
    qb_file = 'staging/2012_parsed/2012_quickbooks_transactions.csv'
    if not os.path.exists(qb_file):
        print(f'File not found: {qb_file}')
        return

    account_names = []
    total_rows = 0
    
    with open(qb_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        print('COLUMN HEADERS:', list(reader.fieldnames))
        
        # Reset and read data
        f.seek(0)
        reader = csv.DictReader(f)
        
        for i, row in enumerate(reader):
            total_rows += 1
            account_name = row.get('account_name', '').strip()
            if account_name:
                account_names.append(account_name)
            
            if i < 5:  # Show first 5 rows
                vendor = row.get('vendor_name', '')
                amount = row.get('gross_amount', '')
                print(f'Row {i+1}: account="{account_name}" vendor="{vendor}" amount="{amount}"')
    
    print(f'\nTOTAL ROWS: {total_rows}')
    print(f'ROWS WITH ACCOUNT NAMES: {len(account_names)}')
    
    if account_names:
        counter = Counter(account_names)
        print('\nTOP 10 ACCOUNT NAMES:')
        for name, count in counter.most_common(10):
            print(f'  "{name}": {count} times')
    
    # Check for expense-related patterns
    expense_patterns = ['expense', 'Expense', 'EXPENSE', 'cost', 'Cost', 'COST']
    expense_accounts = []
    
    for account in set(account_names):
        for pattern in expense_patterns:
            if pattern in account:
                expense_accounts.append(account)
                break
    
    if expense_accounts:
        print(f'\nEXPENSE-RELATED ACCOUNTS ({len(expense_accounts)}):')
        for account in expense_accounts:
            count = counter[account]
            print(f'  "{account}": {count} records')

if __name__ == '__main__':
    main()