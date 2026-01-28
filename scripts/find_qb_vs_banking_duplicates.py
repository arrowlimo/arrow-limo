"""
Find duplicate receipts between QuickBooks imports and auto-created banking receipts.

PATTERN: Same vendor, same amount, dates within 1 day, different sources
- QuickBooks sources: QuickBooks-2012-Import, etc.
- Banking sources: BANKING_IMPORT, CIBC_0228362_Banking, etc.
- created_from_banking flag distinguishes auto-created receipts

KEEP: QuickBooks receipt (actual receipt with detail)
DELETE: Auto-created banking receipt (duplicate)
"""

import pandas as pd
from datetime import timedelta

def main():
    print("Loading receipts export...")
    df = pd.read_excel('L:\\limo\\reports\\receipts_complete_export.xlsx')
    
    print(f"Total receipts: {len(df):,}")
    
    # Convert date
    df['receipt_date'] = pd.to_datetime(df['receipt_date'])
    
    # Identify source types
    df['is_qb_source'] = df['source_system'].str.contains('QuickBooks', case=False, na=False)
    df['is_banking_source'] = (
        df['source_system'].str.contains('BANKING', case=False, na=False) | 
        (df['created_from_banking'] == True)
    )
    
    print(f"\nQuickBooks receipts: {df['is_qb_source'].sum():,}")
    print(f"Banking auto-created receipts: {df['is_banking_source'].sum():,}")
    
    # Sort by vendor, amount, date
    df_sorted = df.sort_values(['vendor_name', 'gross_amount', 'receipt_date'])
    
    print("\n" + "="*80)
    print("FINDING QB vs BANKING DUPLICATES (within 1 day)")
    print("="*80)
    
    duplicates = []
    
    # Group by vendor and amount
    grouped = df_sorted.groupby(['vendor_name', 'gross_amount'])
    
    for (vendor, amount), group in grouped:
        if len(group) < 2:
            continue
            
        # Check each pair in the group
        for i in range(len(group)):
            for j in range(i+1, len(group)):
                row1 = group.iloc[i]
                row2 = group.iloc[j]
                
                # Check date difference (within 1 day)
                date_diff = abs((row1['receipt_date'] - row2['receipt_date']).days)
                if date_diff > 1:
                    continue
                
                # Check if one is QB and one is Banking
                is_qb_banking_pair = (
                    (row1['is_qb_source'] and row2['is_banking_source']) or
                    (row2['is_qb_source'] and row1['is_banking_source'])
                )
                
                if is_qb_banking_pair:
                    # Determine which to keep (QB) and which to delete (Banking)
                    if row1['is_qb_source']:
                        keep = row1
                        delete = row2
                    else:
                        keep = row2
                        delete = row1
                    
                    duplicates.append({
                        'keep_receipt_id': keep['receipt_id'],
                        'keep_date': keep['receipt_date'],
                        'keep_source': keep['source_system'],
                        'delete_receipt_id': delete['receipt_id'],
                        'delete_date': delete['receipt_date'],
                        'delete_source': delete['source_system'],
                        'vendor': vendor,
                        'amount': amount,
                        'date_diff_days': date_diff
                    })
    
    print(f"\nFound {len(duplicates)} QB vs Banking duplicate pairs")
    
    if len(duplicates) == 0:
        print("\n✅ No QB vs Banking duplicates found!")
        return
    
    # Convert to DataFrame
    dupes_df = pd.DataFrame(duplicates)
    
    print("\n" + "="*80)
    print("DUPLICATE PAIRS FOUND")
    print("="*80)
    
    # Show summary by vendor
    print("\nTop vendors with duplicates:")
    vendor_counts = dupes_df['vendor'].value_counts().head(20)
    for vendor, count in vendor_counts.items():
        total_amount = dupes_df[dupes_df['vendor'] == vendor]['amount'].sum()
        print(f"  {vendor}: {count} pairs (${total_amount:,.2f})")
    
    # Show examples
    print("\n" + "="*80)
    print("EXAMPLES (First 20 duplicate pairs)")
    print("="*80)
    
    for idx, row in dupes_df.head(20).iterrows():
        print(f"\n{idx+1}. {row['vendor']} - ${row['amount']:.2f}")
        print(f"   KEEP:   ID {row['keep_receipt_id']} | {row['keep_date'].strftime('%Y-%m-%d')} | {row['keep_source']}")
        print(f"   DELETE: ID {row['delete_receipt_id']} | {row['delete_date'].strftime('%Y-%m-%d')} | {row['delete_source']}")
        print(f"   Date difference: {row['date_diff_days']} day(s)")
    
    # Save deletion list
    deletion_list = dupes_df[['delete_receipt_id', 'vendor', 'amount', 'delete_date', 'delete_source']].copy()
    deletion_list.columns = ['receipt_id', 'vendor', 'amount', 'date', 'source']
    deletion_list['reason'] = 'QB vs Banking duplicate - auto-created banking receipt'
    
    deletion_list.to_csv('L:\\limo\\reports\\qb_banking_duplicates_to_delete.csv', index=False)
    print(f"\n✅ Saved deletion list: L:\\limo\\reports\\qb_banking_duplicates_to_delete.csv")
    
    # Summary statistics
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    print(f"\nTotal duplicate pairs: {len(duplicates)}")
    print(f"Receipts to DELETE (banking auto-created): {len(deletion_list)}")
    print(f"Receipts to KEEP (QuickBooks): {len(deletion_list)}")
    print(f"Total amount affected: ${dupes_df['amount'].sum():,.2f}")
    
    # Date difference distribution
    print("\nDate difference distribution:")
    print(dupes_df['date_diff_days'].value_counts().sort_index())
    
    print("\n" + "="*80)
    print("NEXT STEPS")
    print("="*80)
    print("\n1. Review L:\\limo\\reports\\qb_banking_duplicates_to_delete.csv")
    print("2. Create backup: CREATE TABLE receipts_backup_qb_dedup AS SELECT * FROM receipts;")
    print("3. Delete banking duplicates: DELETE FROM receipts WHERE receipt_id IN (...)")
    print("4. Verify counts and re-export")

if __name__ == '__main__':
    main()
