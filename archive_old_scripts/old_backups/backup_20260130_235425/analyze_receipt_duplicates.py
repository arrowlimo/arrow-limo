"""
Analyze receipt duplicates - distinguish TRUE duplicates from legitimate consecutive transactions.

TRUE DUPLICATE: Same source_hash (exact same transaction imported multiple times)
LEGITIMATE: Same date/vendor/amount but different source_hash (different transactions)
"""

import pandas as pd
import sys

def main():
    print("Loading receipts export...")
    df = pd.read_excel('L:\\limo\\reports\\receipts_complete_export.xlsx')
    
    print(f"Total receipts: {len(df):,}")
    
    # Convert date
    df['receipt_date'] = pd.to_datetime(df['receipt_date'])
    
    # Sort by date, vendor, amount
    df_sorted = df.sort_values(['receipt_date', 'vendor_name', 'gross_amount', 'receipt_id'])
    
    print("\n" + "="*80)
    print("ANALYSIS 1: TRUE DUPLICATES (Same source_hash)")
    print("="*80)
    
    # Find TRUE duplicates by source_hash
    hash_dupes = df_sorted[df_sorted['source_hash'].notna()].groupby('source_hash').size()
    hash_dupes = hash_dupes[hash_dupes > 1].sort_values(ascending=False)
    
    print(f"\nFound {len(hash_dupes)} source_hash values with duplicates")
    print(f"Total TRUE duplicate records: {hash_dupes.sum() - len(hash_dupes):,}")
    
    if len(hash_dupes) > 0:
        print("\nTop 10 TRUE duplicates by source_hash:")
        for hash_val, count in hash_dupes.head(10).items():
            examples = df_sorted[df_sorted['source_hash'] == hash_val][['receipt_id', 'receipt_date', 'vendor_name', 'gross_amount', 'source_system', 'created_at']].head(count)
            print(f"\n  Hash: {hash_val[:16]}... ({count} copies)")
            for idx, row in examples.iterrows():
                print(f"    ID {row['receipt_id']}: {row['receipt_date'].strftime('%Y-%m-%d')} | {row['vendor_name']} | ${row['gross_amount']:.2f} | {row['source_system']} | Created: {row['created_at']}")
    
    print("\n" + "="*80)
    print("ANALYSIS 2: SAME DATE/VENDOR/AMOUNT (May be legitimate)")
    print("="*80)
    
    # Find same date/vendor/amount (could be legitimate)
    potential_dupes = df_sorted.groupby(['receipt_date', 'vendor_name', 'gross_amount']).size()
    potential_dupes = potential_dupes[potential_dupes > 1].sort_values(ascending=False)
    
    print(f"\nFound {len(potential_dupes)} groups with same date/vendor/amount")
    print(f"Total records in these groups: {potential_dupes.sum():,}")
    
    print("\nTop 20 groups (checking if TRUE duplicates or legitimate):")
    for (date, vendor, amount), count in potential_dupes.head(20).items():
        mask = (df_sorted['receipt_date'] == date) & (df_sorted['vendor_name'] == vendor) & (df_sorted['gross_amount'] == amount)
        examples = df_sorted[mask][['receipt_id', 'source_hash', 'source_system', 'created_at']]
        
        # Check if truly duplicates (same hash) or legitimate (different hashes)
        unique_hashes = examples['source_hash'].nunique()
        
        status = "TRUE DUPLICATES" if unique_hashes == 1 else f"LEGITIMATE ({unique_hashes} different hashes)"
        
        print(f"\n  {date.strftime('%Y-%m-%d')} | {vendor} | ${amount:.2f} ({count} records) - {status}")
        for idx, row in examples.iterrows():
            hash_display = str(row['source_hash'])[:16] + "..." if pd.notna(row['source_hash']) else "NO HASH"
            print(f"    ID {row['receipt_id']}: {hash_display} | {row['source_system']} | {row['created_at']}")
    
    print("\n" + "="*80)
    print("ANALYSIS 3: NULL source_hash (Cannot verify)")
    print("="*80)
    
    null_hash_count = df_sorted['source_hash'].isna().sum()
    print(f"\nReceipts with NULL source_hash: {null_hash_count:,} ({null_hash_count/len(df_sorted)*100:.1f}%)")
    
    if null_hash_count > 0:
        print("\nThese cannot be verified as duplicates without source_hash")
        null_hash = df_sorted[df_sorted['source_hash'].isna()]
        print(f"Source systems with NULL hash:")
        print(null_hash['source_system'].value_counts())
    
    print("\n" + "="*80)
    print("RECOMMENDED ACTION")
    print("="*80)
    print("\n1. DELETE receipts with duplicate source_hash (keep oldest by receipt_id)")
    print("2. KEEP receipts with same date/vendor/amount but different source_hash (legitimate)")
    print("3. MANUAL REVIEW receipts with NULL source_hash that match date/vendor/amount")
    
    # Generate deletion candidates
    print("\n" + "="*80)
    print("DELETION CANDIDATES (TRUE DUPLICATES)")
    print("="*80)
    
    deletion_candidates = []
    for hash_val, count in hash_dupes.items():
        dupes = df_sorted[df_sorted['source_hash'] == hash_val].sort_values('receipt_id')
        # Keep first (oldest receipt_id), delete rest
        to_delete = dupes.iloc[1:]['receipt_id'].tolist()
        deletion_candidates.extend(to_delete)
    
    print(f"\nTotal receipts to DELETE: {len(deletion_candidates):,}")
    print(f"Receipts to KEEP: {len(df_sorted) - len(deletion_candidates):,}")
    
    # Save deletion list
    if len(deletion_candidates) > 0:
        deletion_df = pd.DataFrame({
            'receipt_id': deletion_candidates,
            'reason': 'Duplicate source_hash'
        })
        deletion_df.to_csv('L:\\limo\\reports\\receipts_to_delete.csv', index=False)
        print(f"\nSaved deletion list to: L:\\limo\\reports\\receipts_to_delete.csv")
        
        print("\n" + "="*80)
        print("NEXT STEPS")
        print("="*80)
        print("\n1. Review L:\\limo\\reports\\receipts_to_delete.csv")
        print("2. Create backup of receipts table")
        print("3. Run deletion script to remove TRUE duplicates")
        print("4. Re-export clean data")

if __name__ == '__main__':
    main()
