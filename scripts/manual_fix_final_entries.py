#!/usr/bin/env python3
"""
Manual fix for the final 2 HOT TUB WHOLESALE entries.
"""
import pandas as pd

def main():
    final_file = r'l:\limo\reports\receipts_color_coded_FINAL.xlsx'
    fixed_file = r'l:\limo\reports\receipts_color_coded_FIXED.xlsx'
    
    print("🔧 MANUAL FIX FOR FINAL 2 ENTRIES")
    print("=" * 80)
    
    # Load file
    print(f"\n📂 Loading: {final_file}")
    df = pd.read_excel(final_file)
    
    # Find the 2 remaining corrupted entries
    corrupted_mask = df['VENDOR'].str.upper().str.contains('HOT TUB WHOLESALE', na=False)
    corrupted_count = corrupted_mask.sum()
    
    print(f"   Found {corrupted_count} entries with HOT TUB WHOLESALE")
    
    if corrupted_count == 0:
        print("\n✅ No corruption found! File is clean.")
        return
    
    # Show them
    print("\n📋 Corrupted entries:")
    for idx, row in df[corrupted_mask].iterrows():
        date = pd.to_datetime(row['Date'])
        amount = row.get('Withdrawal', row.get('Deposit', 0))
        print(f"   Index {idx}: Date: {date.date()} Amount: ${amount} Category: {row.get('Category', 'N/A')}")
        
        # Fix based on analysis
        if date.year == 2019 and date.month == 3 and date.day == 25:
            # This is ACTUALLY Hot Tub Wholesale - keep it
            print(f"      → Keeping HOT TUB WHOLESALE (legitimate)")
        elif date.year == 2025 and date.month == 10:
            # This is a withdrawal - likely cash or unknown
            print(f"      → Changing to 'Cash Withdrawal' (no banking match found)")
            df.loc[idx, 'VENDOR'] = 'Cash Withdrawal'
        else:
            print(f"      → Changing to 'Unknown' (no match found)")
            df.loc[idx, 'VENDOR'] = 'Unknown'
    
    # Save
    print(f"\n💾 Saving fixed file: {fixed_file}")
    df.to_excel(fixed_file, index=False)
    
    # Final count
    final_corrupted = df['VENDOR'].str.upper().str.contains('HOT TUB WHOLESALE', na=False).sum()
    
    print("\n✅ MANUAL FIX COMPLETE!")
    print(f"\n📊 FINAL STATISTICS:")
    print(f"   Total receipts: {len(df):,}")
    print(f"   HOT TUB WHOLESALE entries: {final_corrupted}")
    print(f"   (Note: Legitimate Hot Tub Wholesale receipts are OK)")
    
    print(f"\n📁 Final file: {fixed_file}")

if __name__ == '__main__':
    main()
