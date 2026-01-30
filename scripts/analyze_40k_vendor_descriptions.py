#!/usr/bin/env python3
"""
Extract vendor descriptions for the ~$40,000 transactions to identify the actual vendors.
"""

import psycopg2
import os
import re

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REDACTED***')
    )

def analyze_40k_vendor_descriptions():
    print("🚗 VENDOR DESCRIPTIONS FOR ~$40,000 TRANSACTIONS")
    print("=" * 55)
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Get the large transactions around $40K
        cur.execute("""
            SELECT 
                bt.transaction_id,
                bt.transaction_date,
                bt.description,
                bt.debit_amount,
                bt.credit_amount,
                bt.vendor_extracted,
                bt.category
            FROM banking_transactions bt
            WHERE EXTRACT(YEAR FROM bt.transaction_date) = 2012
              AND bt.account_number IN ('0228362', '903990106011', '3648117')
              AND COALESCE(bt.debit_amount, bt.credit_amount, 0) >= 35000
              AND COALESCE(bt.debit_amount, bt.credit_amount, 0) <= 45000
            ORDER BY COALESCE(bt.debit_amount, bt.credit_amount) DESC
        """)
        
        large_transactions = cur.fetchall()
        
        print(f"Found {len(large_transactions)} transactions between $35K-$45K\n")
        
        for i, (trans_id, date, desc, debit, credit, vendor, category) in enumerate(large_transactions):
            amount = debit if debit else credit
            
            print(f"💰 TRANSACTION #{i+1}")
            print(f"    Amount: ${amount:,.2f}")
            print(f"    Date: {date}")
            print(f"    Transaction ID: {trans_id}")
            print()
            print(f"    📋 FULL DESCRIPTION:")
            print(f"    \"{desc}\"")
            print()
            print(f"    🏢 VENDOR EXTRACTED:")
            print(f"    \"{vendor}\"" if vendor else "    None - vendor not extracted")
            print()
            print(f"    📂 CATEGORY:")
            print(f"    \"{category}\"" if category else "    Uncategorized")
            print()
            
            # Parse the description for clues
            if desc:
                print(f"    🔍 DESCRIPTION ANALYSIS:")
                
                # Extract reference numbers
                ref_numbers = re.findall(r'\d{6,}', desc)
                if ref_numbers:
                    print(f"    • Reference Numbers: {ref_numbers}")
                
                # Look for vendor codes (3-digit numbers)
                vendor_codes = re.findall(r'\b\d{3}\b', desc)
                if vendor_codes:
                    print(f"    • Potential Vendor Codes: {vendor_codes}")
                
                # Look for vehicle/product codes
                vehicle_codes = re.findall(r'\b[A-Z]{2}\s*\d*', desc)
                if vehicle_codes:
                    print(f"    • Vehicle/Product Codes: {vehicle_codes}")
                
                # Check for specific patterns
                desc_upper = desc.upper()
                if 'VV' in desc_upper:
                    print(f"    • VV Code: Likely vehicle-related transaction")
                if 'VY' in desc_upper:
                    print(f"    • VY Code: Likely vehicle-related transaction")
                if '+' in desc:
                    print(f"    • Plus Sign: Additional charges/options included")
                
                # Try to interpret the structure
                parts = desc.split()
                print(f"    • Description Parts: {parts}")
                
                if len(parts) >= 2 and parts[0].startswith('PURCHASE'):
                    purchase_code = parts[0].replace('PURCHASE', '')
                    if purchase_code:
                        print(f"    • Purchase Code: \"{purchase_code}\"")
                
                # Look for potential dealer indicators
                dealer_patterns = {
                    '390': 'Possible Ford dealer (390 area code/region)',
                    '073': 'Possible dealer code 073', 
                    'VV': 'Vehicle code - likely limousine/commercial',
                    'VY': 'Vehicle code - possibly different model'
                }
                
                for pattern, meaning in dealer_patterns.items():
                    if pattern in desc_upper:
                        print(f"    • {pattern}: {meaning}")
            
            print(f"    {'-' * 60}")
            print()
        
        # Analyze the codes for patterns
        print(f"\n🔍 CODE PATTERN ANALYSIS:")
        print("=" * 30)
        
        all_codes = []
        all_refs = []
        
        for trans_id, date, desc, debit, credit, vendor, category in large_transactions:
            if desc:
                # Extract codes
                codes = re.findall(r'PURCHASE(\d{3})', desc)
                refs = re.findall(r'\d{10,}', desc)
                
                all_codes.extend(codes)
                all_refs.extend(refs)
        
        if all_codes:
            unique_codes = list(set(all_codes))
            print(f"Vendor Codes Found: {unique_codes}")
            
            # Interpret codes
            code_interpretations = {
                '390': 'Possible Ford/Lincoln dealer (Saskatchewan area)',
                '073': 'Different dealer/vendor code',
                '000': 'Generic purchase code'
            }
            
            for code in unique_codes:
                interpretation = code_interpretations.get(code, 'Unknown vendor code')
                print(f"  Code {code}: {interpretation}")
        
        if all_refs:
            print(f"\nReference Numbers: {list(set(all_refs))}")
            print("These may be:")
            print("  • Dealer invoice numbers")
            print("  • Vehicle identification numbers")
            print("  • Purchase order numbers")
            print("  • Financing reference numbers")
        
        # Check for business context
        print(f"\n🚗 BUSINESS CONTEXT ANALYSIS:")
        print("=" * 35)
        
        total_40k = sum(float(t[3] or t[4]) for t in large_transactions)
        
        print(f"Total ~$40K purchases: ${total_40k:,.2f}")
        print(f"Average amount: ${total_40k/len(large_transactions):,.2f}")
        print(f"Date range: {min(t[1] for t in large_transactions)} to {max(t[1] for t in large_transactions)}")
        
        # Check timing
        dates = [t[1] for t in large_transactions]
        date_range = max(dates) - min(dates)
        if date_range.days <= 5:  # Within 5 days
            print(f"[WARN]  All purchases within {date_range.days} days - coordinated fleet acquisition!")
        else:
            print(f"Purchase spread: {date_range.days} days")
        
        print(f"\n💡 VENDOR INTERPRETATION:")
        print("=" * 25)
        print("Based on the patterns:")
        print("• Code 390: Likely primary vehicle dealer (Ford/Lincoln)")
        print("• Code 073: Secondary dealer or different vehicle type") 
        print("• VV/VY codes: Different vehicle models/configurations")
        print("• Sequential dates: Coordinated purchase (fleet expansion)")
        print("• Similar amounts: Standard limousine pricing")
        
        print(f"\n🎯 RECOMMENDED VENDOR RESEARCH:")
        print("=" * 35)
        print("1. Search Saskatchewan Ford/Lincoln dealers active in 2012")
        print("2. Look for dealer codes 390 and 073 in automotive databases")
        print("3. Check vehicle registration records for April 2012 additions")
        print("4. Cross-reference with insurance policy vehicle additions")
        
        # Check if we can find more vendor info in other tables
        print(f"\n🔍 CHECKING OTHER SYSTEM DATA:")
        print("=" * 32)
        
        # Check receipts table for any Ford/vehicle related entries
        cur.execute("""
            SELECT vendor_name, description, gross_amount 
            FROM receipts 
            WHERE EXTRACT(YEAR FROM receipt_date) = 2012
              AND (UPPER(vendor_name) LIKE '%FORD%' 
                   OR UPPER(vendor_name) LIKE '%AUTO%'
                   OR UPPER(vendor_name) LIKE '%DEALER%'
                   OR UPPER(vendor_name) LIKE '%MOTOR%'
                   OR UPPER(description) LIKE '%VEHICLE%'
                   OR UPPER(description) LIKE '%CAR%')
            ORDER BY gross_amount DESC
        """)
        
        vehicle_receipts = cur.fetchall()
        
        if vehicle_receipts:
            print("Found vehicle-related receipts in 2012:")
            for vendor, desc, amount in vehicle_receipts[:10]:  # Top 10
                print(f"  {vendor}: ${amount:,.2f} - {desc[:50]}...")
        else:
            print("No vehicle-related receipts found in receipts table for 2012")
            print("→ This confirms these $40K transactions need to be receipted")
        
    except Exception as e:
        print(f"\n[FAIL] ERROR: {str(e)}")
        raise
        
    finally:
        cur.close()
        conn.close()

def main():
    analyze_40k_vendor_descriptions()

if __name__ == "__main__":
    main()