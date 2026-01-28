#!/usr/bin/env python3
"""
Review and potentially fix the multiple matches from recovery.
"""
import pandas as pd

def main():
    recovered_file = r'l:\limo\reports\receipts_color_coded_RECOVERED.xlsx'
    
    print("📊 REVIEWING MULTIPLE MATCHES")
    print("=" * 80)
    
    # Load recovered file
    print(f"\n📂 Loading: {recovered_file}")
    df = pd.read_excel(recovered_file)
    
    # Find multiple matches
    multiple_mask = df['VENDOR'].str.contains('[MULTIPLE_MATCHES]', regex=False, na=False)
    multiple_count = multiple_mask.sum()
    
    print(f"   Total receipts: {len(df):,}")
    print(f"   Multiple matches: {multiple_count:,}")
    
    if multiple_count == 0:
        print("\n✅ No multiple matches to review!")
        return
    
    # Show examples
    print("\n📋 First 30 multiple match examples:")
    print("=" * 160)
    
    multiple_df = df[multiple_mask].head(30)
    for idx, row in multiple_df.iterrows():
        date = str(row.get('Date', 'N/A'))[:10]
        vendor = row['VENDOR']
        amount_w = row.get('Withdrawal', 0)
        amount_d = row.get('Deposit', 0)
        amount = amount_w if amount_w != 0 else amount_d
        category = row.get('Category', 'N/A')
        payment = row.get('Payment Method', 'N/A')
        
        print(f"Date: {date:<12} Vendor: {vendor:<60} Amount: ${amount:>10.2f} Cat: {category:<20} Pay: {payment}")
    
    # Show vendor breakdown
    print("\n📂 Vendors with multiple matches:")
    vendors = df[multiple_mask]['VENDOR'].str.replace(' [MULTIPLE_MATCHES]', '', regex=False).value_counts()
    for vendor, count in vendors.head(20).items():
        print(f"  {vendor:<50} {count:>4}")
    
    print(f"\n💡 Recommendation:")
    print(f"   1. Review the {multiple_count} flagged entries manually")
    print(f"   2. Use Date + Amount + Category + Payment Method to refine matches")
    print(f"   3. OR accept the first match (already populated) if it looks reasonable")
    print(f"   4. Remove [MULTIPLE_MATCHES] flag when satisfied")

if __name__ == '__main__':
    main()
