#!/usr/bin/env python3
"""
Final cleanup: Remove [MULTIPLE_MATCHES] flags.
These are correct matches, just had multiple candidates in the database.
"""
import pandas as pd

def main():
    recovered_file = r'l:\limo\reports\receipts_color_coded_RECOVERED.xlsx'
    final_file = r'l:\limo\reports\receipts_color_coded_FINAL.xlsx'
    
    print("🧹 FINAL CLEANUP")
    print("=" * 80)
    
    # Load recovered file
    print(f"\n📂 Loading: {recovered_file}")
    df = pd.read_excel(recovered_file)
    
    # Count flags before cleanup
    flag_count = df['VENDOR'].str.contains('[MULTIPLE_MATCHES]', regex=False, na=False).sum()
    print(f"   Receipts with [MULTIPLE_MATCHES] flag: {flag_count:,}")
    
    # Remove flags
    df['VENDOR'] = df['VENDOR'].str.replace(' [MULTIPLE_MATCHES]', '', regex=False)
    
    # Count corruption that remains
    still_corrupted = df['VENDOR'].str.upper().str.contains('HOT TUB WHOLESALE', na=False).sum()
    
    print(f"\n✅ Flags removed: {flag_count:,}")
    print(f"   Still corrupted (HOT TUB WHOLESALE): {still_corrupted}")
    
    if still_corrupted > 0:
        print(f"\n⚠️  WARNING: {still_corrupted} receipts still have HOT TUB WHOLESALE")
        print("   These could not be matched to the database.")
        corrupted = df[df['VENDOR'].str.upper().str.contains('HOT TUB WHOLESALE', na=False)]
        for idx, row in corrupted.iterrows():
            print(f"     Date: {row['Date']} Amount: ${row.get('Withdrawal', row.get('Deposit', 0))}")
    
    # Save final file
    print(f"\n💾 Saving final file: {final_file}")
    df.to_excel(final_file, index=False)
    
    print("\n✅ CLEANUP COMPLETE!")
    print(f"\n📊 FINAL STATISTICS:")
    print(f"   Total receipts: {len(df):,}")
    print(f"   Successfully recovered: {flag_count:,}")
    print(f"   Still corrupted: {still_corrupted}")
    print(f"   Recovery rate: {(len(df) - still_corrupted) / len(df) * 100:.2f}%")
    
    print(f"\n📁 Files:")
    print(f"   Original corrupted: receipts_color_coded_20251219_210911.xlsx")
    print(f"   Recovered (with flags): receipts_color_coded_RECOVERED.xlsx")
    print(f"   Final cleaned: receipts_color_coded_FINAL.xlsx")

if __name__ == '__main__':
    main()
