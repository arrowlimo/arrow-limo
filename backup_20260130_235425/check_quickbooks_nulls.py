#!/usr/bin/env python3
"""
Check QuickBooks data for null values that could cause import errors.
"""

import pandas as pd
import numpy as np

def main():
    # Load and check data
    qb_file = 'l:\\limo\\staging\\2012_parsed\\2012_quickbooks_transactions.csv'
    qb_data = pd.read_csv(qb_file)

    # Filter to expense transactions
    expenses = qb_data[qb_data['withdrawal'].notna() & (qb_data['withdrawal'] > 0)].copy()
    expenses_2012 = expenses[pd.to_datetime(expenses['date'], format='%m/%d/%Y', errors='coerce').dt.year == 2012].copy()

    print(f'Total 2012 expenses: {len(expenses_2012)}')
    print(f'Withdrawal column info:')
    print(f'  Non-null: {expenses_2012["withdrawal"].notna().sum()}')
    print(f'  Null/NaN: {expenses_2012["withdrawal"].isna().sum()}')
    print(f'  Data types: {expenses_2012["withdrawal"].dtype}')

    # Check for any null values after processing
    expenses_2012['vendor_name'] = expenses_2012['description'].str.strip().str[:200]
    expenses_2012['gross_amount'] = expenses_2012['withdrawal']

    print(f'\nAfter processing:')
    print(f'  gross_amount nulls: {expenses_2012["gross_amount"].isna().sum()}')
    print(f'  vendor_name nulls: {expenses_2012["vendor_name"].isna().sum()}')

    # Calculate GST
    expenses_2012['gst_amount'] = expenses_2012['gross_amount'] * 0.05 / 1.05
    expenses_2012['net_amount'] = expenses_2012['gross_amount'] - expenses_2012['gst_amount']
    
    print(f'  gst_amount nulls: {expenses_2012["gst_amount"].isna().sum()}')
    print(f'  net_amount nulls: {expenses_2012["net_amount"].isna().sum()}')

    # Check specific problematic values
    null_amounts = expenses_2012[expenses_2012['gross_amount'].isna()]
    if len(null_amounts) > 0:
        print(f'\nRows with null amounts:')
        for idx, row in null_amounts.head().iterrows():
            print(f'  Row {idx}: date={row["date"]}, description={row["description"]}, withdrawal={row["withdrawal"]}')

    # Check first few rows that would be processed
    print(f'\nFirst 5 rows to be imported:')
    for i, (idx, row) in enumerate(expenses_2012.head().iterrows()):
        vendor = str(row["vendor_name"])[:30] if pd.notna(row["vendor_name"]) else "None"
        amount = row["gross_amount"] if pd.notna(row["gross_amount"]) else "None"
        gst = row["gst_amount"] if pd.notna(row["gst_amount"]) else "None"
        net = row["net_amount"] if pd.notna(row["net_amount"]) else "None"
        print(f'  {i+1}. {row["date"]} | {vendor} | gross:{amount} gst:{gst} net:{net}')

if __name__ == '__main__':
    main()