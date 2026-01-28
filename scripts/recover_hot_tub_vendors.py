#!/usr/bin/env python3
"""
Recover vendor names corrupted by HOT TUB WHOLESALE overwrite.

Strategy:
1. Load the corrupted Excel file
2. For each HOT TUB WHOLESALE entry, match to database by:
   - Date (exact match)
   - Amount (withdrawal or deposit, exact match)
   - Category (if available)
3. Restore correct vendor name from database
4. Save recovered data to new Excel file
"""
import pandas as pd
import psycopg2
from datetime import datetime
import sys

DB_CONFIG = {
    'host': 'localhost',
    'database': 'almsdata',
    'user': 'postgres',
    'password': '***REMOVED***'
}

def main():
    corrupted_file = r'l:\limo\reports\receipts_color_coded_20251219_210911.xlsx'
    recovered_file = r'l:\limo\reports\receipts_color_coded_RECOVERED.xlsx'
    
    print("🔧 HOT TUB WHOLESALE VENDOR NAME RECOVERY")
    print("=" * 80)
    
    # Load corrupted Excel file
    print(f"\n📂 Loading corrupted file: {corrupted_file}")
    df = pd.read_excel(corrupted_file)
    print(f"   Total receipts: {len(df):,}")
    
    # Find corrupted entries
    corrupted_mask = df['VENDOR'].str.upper().str.contains('HOT TUB WHOLESALE', na=False)
    corrupted_count = corrupted_mask.sum()
    print(f"   Corrupted entries: {corrupted_count:,} ({corrupted_count/len(df)*100:.1f}%)")
    
    if corrupted_count == 0:
        print("\n✅ No corruption found!")
        return
    
    # Connect to database
    print("\n🔌 Connecting to database...")
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    # Get all receipts from database
    print("📥 Loading all receipts from database...")
    cur.execute("""
        SELECT 
            receipt_date,
            vendor_name,
            gross_amount,
            category,
            description,
            payment_method,
            expense_account,
            gst_amount,
            vehicle_id,
            vehicle_number
        FROM receipts
        WHERE vendor_name IS NOT NULL 
          AND UPPER(vendor_name) NOT LIKE '%HOT TUB WHOLESALE%'
        ORDER BY receipt_date
    """)
    
    db_receipts = cur.fetchall()
    print(f"   Database receipts: {len(db_receipts):,}")
    
    # Create lookup dictionary: (date, amount) -> vendor_name
    print("\n🗂️  Building lookup index...")
    lookup = {}
    for row in db_receipts:
        date, vendor, amount, cat, desc, pay, exp, gst, vid, vnum = row
        key = (date, abs(float(amount)) if amount else 0)
        if key not in lookup:
            lookup[key] = []
        lookup[key].append({
            'vendor': vendor,
            'category': cat,
            'description': desc,
            'payment_method': pay,
            'gst_amount': gst
        })
    
    print(f"   Lookup entries: {len(lookup):,}")
    
    # Recover vendor names
    print("\n🔄 Recovering vendor names...")
    recovered = 0
    multiple_matches = 0
    no_matches = 0
    
    for idx in df[corrupted_mask].index:
        row = df.loc[idx]
        
        # Parse date
        try:
            date = pd.to_datetime(row['Date']).date()
        except:
            no_matches += 1
            continue
        
        # Get amount (check both withdrawal and deposit)
        amount = 0
        if pd.notna(row.get('Withdrawal')) and row.get('Withdrawal') != 0:
            amount = abs(float(row['Withdrawal']))
        elif pd.notna(row.get('Deposit')) and row.get('Deposit') != 0:
            amount = abs(float(row['Deposit']))
        
        # Look up in database
        key = (date, amount)
        
        if key in lookup:
            matches = lookup[key]
            
            if len(matches) == 1:
                # Single match - use it
                df.loc[idx, 'VENDOR'] = matches[0]['vendor']
                recovered += 1
            else:
                # Multiple matches - try to narrow down by category
                cat = str(row.get('Category', '')).strip() if pd.notna(row.get('Category')) else ''
                filtered = [m for m in matches if m['category'] == cat]
                
                if len(filtered) == 1:
                    df.loc[idx, 'VENDOR'] = filtered[0]['vendor']
                    recovered += 1
                else:
                    # Use first match and flag
                    df.loc[idx, 'VENDOR'] = matches[0]['vendor'] + ' [MULTIPLE_MATCHES]'
                    multiple_matches += 1
        else:
            no_matches += 1
        
        # Progress
        if (idx % 1000) == 0:
            print(f"   Progress: {idx:,}/{len(df):,} ({idx/len(df)*100:.1f}%)")
    
    # Summary
    print("\n📊 RECOVERY SUMMARY:")
    print(f"   ✅ Recovered: {recovered:,}")
    print(f"   ⚠️  Multiple matches: {multiple_matches:,}")
    print(f"   ❌ No matches: {no_matches:,}")
    print(f"   📈 Recovery rate: {recovered/corrupted_count*100:.1f}%")
    
    # Save recovered file
    print(f"\n💾 Saving recovered file: {recovered_file}")
    df.to_excel(recovered_file, index=False)
    
    print("\n✅ RECOVERY COMPLETE!")
    print(f"\n📁 Original file: {corrupted_file}")
    print(f"📁 Recovered file: {recovered_file}")
    
    # Close database
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
