#!/usr/bin/env python3
"""
Analyze HOT TUB WHOLESALE corruption in receipts Excel file
"""
import pandas as pd
import psycopg2
import os

def main():
    file_path = r'l:\limo\reports\receipts_color_coded_20251219_210911.xlsx'
    
    print("📊 ANALYZING HOT TUB WHOLESALE CORRUPTION\n")
    
    # Read the Excel file
    print(f"Reading: {file_path}")
    df = pd.read_excel(file_path)
    
    # Show column names
    print(f"\n📋 Columns in Excel file:")
    for i, col in enumerate(df.columns, 1):
        print(f"  {i}. {col}")
    
    # Find vendor column (might be named differently)
    vendor_col = None
    for col in df.columns:
        if 'vendor' in col.lower():
            vendor_col = col
            break
    
    if not vendor_col:
        print("\n❌ No vendor column found!")
        return
    
    print(f"\n✅ Using vendor column: '{vendor_col}'")
    
    # Find all rows with HOT TUB WHOLESALE
    hot_tub_mask = df[vendor_col].str.upper().str.contains('HOT TUB WHOLESALE', na=False)
    hot_tub_count = hot_tub_mask.sum()
    
    print(f'\n🚨 CORRUPTION ANALYSIS:')
    print(f'Total receipts in file: {len(df):,}')
    print(f'Receipts with HOT TUB WHOLESALE: {hot_tub_count:,}')
    print(f'Corruption rate: {hot_tub_count/len(df)*100:.1f}%\n')
    
    if hot_tub_count > 0:
        print('First 30 corrupted entries:')
        print('=' * 160)
        hot_tub_receipts = df[hot_tub_mask].head(30)
        for idx, row in hot_tub_receipts.iterrows():
            rec_id = row.get('receipt_id', row.get('Receipt ID', 'N/A'))
            rec_date = str(row.get('receipt_date', row.get('Date', 'N/A')))[:10]
            vendor = row[vendor_col]
            amount = row.get('gross_amount', row.get('Amount', row.get('Gross Amount', 0)))
            banking_id = row.get('banking_transaction_id', row.get('Banking ID', 'N/A'))
            category = row.get('category', row.get('Category', 'N/A'))
            print(f"ID: {rec_id:<8} Date: {rec_date:<12} Vendor: {vendor:<35} Amount: ${amount:>10.2f} Banking: {banking_id:<8} Cat: {category}")
        
        # Check if there are banking_transaction_ids to help recover
        banking_col = 'banking_transaction_id' if 'banking_transaction_id' in df.columns else 'Banking ID' if 'Banking ID' in df.columns else None
        if banking_col:
            has_banking_id = hot_tub_receipts[banking_col].notna().sum()
            print(f'\n📌 {has_banking_id} corrupted receipts have banking_transaction_id (can recover from banking table)')
        
        # Show date range
        date_col = 'receipt_date' if 'receipt_date' in df.columns else 'Date'
        dates = pd.to_datetime(df[hot_tub_mask][date_col])
        print(f'📅 Corruption date range: {dates.min()} to {dates.max()}')
        
        # Show categories
        cat_col = 'category' if 'category' in df.columns else 'Category' if 'Category' in df.columns else None
        if cat_col:
            categories = df[hot_tub_mask][cat_col].value_counts()
            print(f'\n📂 Categories affected:')
            for cat, count in categories.items():
                print(f'  {cat}: {count}')

if __name__ == '__main__':
    main()
