#!/usr/bin/env python3
"""
Compare QuickBooks GlobalPayments fees with CIBC account withdrawals
to identify missing months and actual withdrawal dates.
"""

import pandas as pd
from datetime import datetime

def compare_qb_fees_with_cibc():
    """Compare QuickBooks fees with CIBC account data."""
    
    print("🔍 COMPARING QUICKBOOKS FEES WITH CIBC WITHDRAWALS")
    print("=" * 60)
    
    # Load CIBC data
    try:
        cibc_df = pd.read_csv('l:/limo/staging/2012_parsed/2012_cibc_transactions.csv')
        print(f"Loaded {len(cibc_df):,} CIBC transactions for 2012")
    except Exception as e:
        print(f"Error loading CIBC data: {e}")
        return
    
    # QuickBooks GlobalPayments fees found
    qb_fees = [
        {'amount': '1244.81', 'qb_date': '2012-02-06', 'month': 'Feb'},
        {'amount': '1069.62', 'qb_date': '2012-03-01', 'month': 'Mar'},
        {'amount': '791.87', 'qb_date': '2012-04-02', 'month': 'Apr'},
        {'amount': '1170.45', 'qb_date': '2012-05-01', 'month': 'May'},
        {'amount': '1721.82', 'qb_date': '2012-06-01', 'month': 'Jun'},
        {'amount': '392.45', 'qb_date': '2012-08-01', 'month': 'Aug'},
        {'amount': '288.62', 'qb_date': '2012-09-04', 'month': 'Sep'},
        {'amount': '367.50', 'qb_date': '2012-09-06', 'month': 'Sep'},
        {'amount': '423.85', 'qb_date': '2012-11-01', 'month': 'Nov'},
        {'amount': '309.65', 'qb_date': '2012-12-03', 'month': 'Dec'}
    ]
    
    print(f"\nQuickBooks shows {len(qb_fees)} GlobalPayments fee entries")
    print("Total QB fees: ${:,.2f}".format(sum(float(f['amount']) for f in qb_fees)))
    
    # Check which months are covered
    months_with_fees = set(f['month'] for f in qb_fees)
    all_months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 
                  'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    missing_months = [m for m in all_months if m not in months_with_fees]
    
    print(f"\nMonths with fees: {', '.join(sorted(months_with_fees))}")
    print(f"Missing months: {', '.join(missing_months)}")
    
    # Search CIBC data for each fee amount
    print(f"\n📅 SEARCHING FOR FEES IN CIBC DATA:")
    print("-" * 50)
    
    found_count = 0
    
    for fee in qb_fees:
        amount = fee['amount']
        qb_date = fee['qb_date']
        month = fee['month']
        
        # Search for this amount in CIBC descriptions
        # Check for various formats due to OCR
        dollar_part = amount.split('.')[0]
        cent_part = amount.split('.')[1] if '.' in amount else '00'
        
        search_patterns = [
            amount,                          # 1244.81
            f"{dollar_part}.{cent_part}",   # 1244.81
            f"{dollar_part},{cent_part}",   # 1244,81
            dollar_part,                     # 1244
            f"{dollar_part} {cent_part}",   # 1244 81
        ]
        
        found = False
        for pattern in search_patterns:
            matches = cibc_df[cibc_df['description'].str.contains(pattern, case=False, na=False)]
            
            if len(matches) > 0:
                found = True
                found_count += 1
                print(f"✓ ${amount} ({month}, QB: {qb_date})")
                for _, match in matches.iterrows():
                    print(f"   CIBC: {match['date']} - {match['description'][:60]}...")
                break
        
        if not found:
            print(f"✗ ${amount} ({month}, QB: {qb_date}) - NOT FOUND in CIBC")
    
    print(f"\n📊 SUMMARY:")
    print(f"Fees found in CIBC: {found_count}/{len(qb_fees)}")
    print(f"Fees missing from CIBC: {len(qb_fees) - found_count}")
    
    # Check for large withdrawals in missing months
    print(f"\n🔍 LARGE WITHDRAWALS IN MISSING MONTHS:")
    print("-" * 45)
    
    for month_name in missing_months:
        month_num = all_months.index(month_name) + 1
        
        # Filter CIBC data for this month
        month_filter = cibc_df['date'].str.contains(f'2012.*{month_num:02d}', na=False)
        month_data = cibc_df[month_filter]
        
        if len(month_data) > 0:
            # Look for significant withdrawals (could be fees)
            month_data['withdrawal_num'] = pd.to_numeric(
                month_data['withdrawal'].str.replace(',', ''), errors='coerce'
            )
            
            large_withdrawals = month_data[
                (month_data['withdrawal_num'] > 200) & 
                (month_data['withdrawal_num'] < 5000)
            ]
            
            if len(large_withdrawals) > 0:
                print(f"\n{month_name} 2012 large withdrawals:")
                for _, row in large_withdrawals.iterrows():
                    print(f"  {row['date']} ${row['withdrawal_num']:,.2f} - {row['description'][:50]}...")
            else:
                print(f"\n{month_name} 2012: No large withdrawals found")
        else:
            print(f"\n{month_name} 2012: No CIBC data available")


if __name__ == "__main__":
    compare_qb_fees_with_cibc()