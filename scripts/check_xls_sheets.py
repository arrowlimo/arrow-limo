#!/usr/bin/env python3
import pandas as pd

xls = pd.ExcelFile('l:/limo/reports/cheque_vendor_reference.xlsx')
print('Sheet names:', xls.sheet_names)
print()

for sheet in xls.sheet_names:
    df = pd.read_excel(xls, sheet_name=sheet)
    print(f'{sheet}: {len(df)} rows, {len(df.columns)} columns')
    print(f'  Columns: {list(df.columns)}')
    
    if len(df) > 0 and 'cheque' in str(df.columns).lower():
        print(f'\n  Sample data from {sheet}:')
        pd.set_option('display.max_columns', None)
        pd.set_option('display.width', 200)
        print(df.head(10).to_string(index=False))
    print()
