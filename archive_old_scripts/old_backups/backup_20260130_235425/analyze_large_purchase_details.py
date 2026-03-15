#!/usr/bin/env python3
"""
Detailed analysis of large purchase transactions to determine if they're business or personal.
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

def analyze_large_purchases():
    print("🔍 DETAILED ANALYSIS OF LARGE PURCHASE TRANSACTIONS")
    print("=" * 55)
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Get the large purchase transactions with full details
        cur.execute("""
            SELECT 
                bt.transaction_id,
                bt.transaction_date,
                bt.description,
                bt.debit_amount,
                bt.credit_amount,
                bt.vendor_extracted
            FROM banking_transactions bt
            LEFT JOIN receipts r ON (
                r.receipt_date = bt.transaction_date
                AND ABS(COALESCE(r.gross_amount, 0) - COALESCE(bt.debit_amount, bt.credit_amount, 0)) < 0.01
            )
            WHERE EXTRACT(YEAR FROM bt.transaction_date) = 2012
              AND bt.account_number IN ('0228362', '903990106011', '3648117')
              AND r.id IS NULL
              AND COALESCE(bt.debit_amount, bt.credit_amount, 0) > 0
            ORDER BY COALESCE(bt.debit_amount, bt.credit_amount) DESC
        """)
        
        all_transactions = cur.fetchall()
        
        # Separate by size
        large_transactions = [t for t in all_transactions if (t[3] or t[4] or 0) >= 5000]
        medium_transactions = [t for t in all_transactions if 1000 <= (t[3] or t[4] or 0) < 5000]
        small_transactions = [t for t in all_transactions if 0 < (t[3] or t[4] or 0) < 1000]
        
        print(f"Found {len(all_transactions)} total unmatched transactions:")
        print(f"  Large (≥$5,000): {len(large_transactions)}")
        print(f"  Medium ($1,000-$4,999): {len(medium_transactions)}")
        print(f"  Small (<$1,000): {len(small_transactions)}")
        
        print(f"\n💰 LARGE TRANSACTIONS (≥$5,000) - DETAILED ANALYSIS:")
        print("=" * 55)
        
        large_total = 0
        
        for i, (trans_id, date, desc, debit, credit, vendor) in enumerate(large_transactions):
            amount = debit if debit else credit
            large_total += amount
            
            print(f"\n{i+1}. Transaction ID: {trans_id}")
            print(f"   Date: {date}")
            print(f"   Amount: ${amount:,.2f}")
            print(f"   Description: {desc}")
            print(f"   Vendor: {vendor or 'None extracted'}")
            
            # Analyze the purchase codes for clues
            business_indicators = []
            personal_indicators = []
            
            if desc:
                desc_upper = desc.upper()
                
                # Look for vehicle/business indicators
                if any(word in desc_upper for word in ['VEHICLE', 'AUTO', 'FLEET', 'LIMOUSINE', 'LIMO']):
                    business_indicators.append('Vehicle-related')
                
                # Look for equipment indicators  
                if any(word in desc_upper for word in ['EQUIPMENT', 'COMMERCIAL', 'BUSINESS']):
                    business_indicators.append('Business equipment')
                
                # Look for personal indicators
                if any(word in desc_upper for word in ['PERSONAL', 'HOME', 'HOUSE', 'FAMILY']):
                    personal_indicators.append('Personal purchase')
                
                # Extract reference numbers for potential lookup
                numbers = re.findall(r'\d{6,}', desc)
                if numbers:
                    print(f"   Reference numbers: {numbers}")
                
                # Analyze purchase patterns
                if 'PURCHASE' in desc_upper:
                    # Large purchases in limousine business could be:
                    # 1. Vehicle purchases/down payments
                    # 2. Equipment purchases
                    # 3. Insurance payments
                    # 4. Capital improvements
                    
                    if amount >= 40000:
                        business_indicators.append('Likely vehicle purchase/major equipment')
                    elif amount >= 20000:
                        business_indicators.append('Possible vehicle down payment')
                    elif amount >= 5000:
                        business_indicators.append('Possible business equipment')
            
            # Assess likelihood
            if business_indicators:
                print(f"   📈 BUSINESS indicators: {', '.join(business_indicators)}")
            if personal_indicators:
                print(f"   🏠 PERSONAL indicators: {', '.join(personal_indicators)}")
            
            # Date pattern analysis (business vs personal timing)
            if date:
                if date.weekday() < 5:  # Monday-Friday
                    print(f"   📅 Weekday transaction (business likely)")
                else:
                    print(f"   📅 Weekend transaction (personal more likely)")
            
            # Amount-based assessment for limousine business
            if amount >= 40000:
                print(f"   💡 ASSESSMENT: Likely vehicle purchase or major business investment")
                print(f"      - In limousine business, amounts this large typically vehicles")
                print(f"      - Should be documented as business capital expense")
            elif amount >= 20000:
                print(f"   💡 ASSESSMENT: Possible vehicle down payment or major equipment")
                print(f"      - Could be business investment requiring documentation")
            elif amount >= 10000:
                print(f"   💡 ASSESSMENT: Significant purchase - business equipment likely")
            else:
                print(f"   💡 ASSESSMENT: Medium business expense or personal purchase")
        
        print(f"\n📊 LARGE TRANSACTIONS SUMMARY:")
        print(f"   Total large transactions: {len(large_transactions)}")
        print(f"   Total large amount: ${large_total:,.2f}")
        print(f"   Average large transaction: ${large_total/len(large_transactions):,.2f}" if large_transactions else "N/A")
        
        # Analyze medium transactions
        if medium_transactions:
            print(f"\n💵 MEDIUM TRANSACTIONS ($1,000-$4,999):")
            print("=" * 40)
            
            medium_total = sum(t[3] or t[4] or 0 for t in medium_transactions)
            
            print(f"Count: {len(medium_transactions)}, Total: ${medium_total:,.2f}")
            print("\nSample medium transactions:")
            
            for i, (trans_id, date, desc, debit, credit, vendor) in enumerate(medium_transactions[:8]):
                amount = debit if debit else credit
                desc_short = desc[:50] + "..." if desc and len(desc) > 50 else desc or ""
                print(f"  {i+1}. {date} - ${amount:,.2f} - {desc_short}")
        
        # Business vs Personal Assessment
        print(f"\n🎯 BUSINESS VS PERSONAL ASSESSMENT:")
        print("=" * 40)
        
        # For limousine business context
        likely_business_amount = sum(t[3] or t[4] or 0 for t in large_transactions if (t[3] or t[4] or 0) >= 20000)
        possible_business_amount = sum(t[3] or t[4] or 0 for t in large_transactions if 5000 <= (t[3] or t[4] or 0) < 20000)
        
        print(f"Likely business (vehicles/major equipment ≥$20K): ${likely_business_amount:,.2f}")
        print(f"Possible business (equipment $5K-$20K): ${possible_business_amount:,.2f}")
        
        total_potential_business = likely_business_amount + possible_business_amount
        
        print(f"\n💰 POTENTIAL TAX IMPLICATIONS:")
        if total_potential_business > 0:
            # For business purchases, GST may be recoverable and expense deductible
            potential_gst_recovery = float(total_potential_business) * 0.05 / 1.05  # GST included
            
            print(f"   Potential business purchases: ${total_potential_business:,.2f}")
            print(f"   Potential GST recovery: ${potential_gst_recovery:,.2f}")
            print(f"   Business tax deduction: ${float(total_potential_business) - potential_gst_recovery:,.2f}")
        
        print(f"\n📋 RECOMMENDATIONS:")
        print("1. IMMEDIATE ACTIONS:")
        print("   - Research large transactions with business context")
        print("   - Check if amounts match known vehicle purchases")
        print("   - Verify against insurance/financing records")
        
        print("\n2. DOCUMENTATION NEEDED:")
        print("   - Vehicle purchase agreements for large amounts")
        print("   - Equipment purchase receipts")
        print("   - Financing/loan documentation")
        
        print("\n3. CRA COMPLIANCE:")
        print("   - Large business purchases need proper documentation")
        print("   - Capital expenses may need different tax treatment")
        print("   - Personal purchases should not be receipted as business")
        
        # Check if these might match vehicle financing we've seen
        print(f"\n🚗 VEHICLE CONTEXT CHECK:")
        print("Note: In previous analysis, we found vehicle financing emails.")
        print("These large purchases may correlate with:")
        print("- Vehicle down payments or purchases")
        print("- Insurance premium payments")  
        print("- Major equipment for limousine operations")
        
    except Exception as e:
        print(f"\n[FAIL] ERROR: {str(e)}")
        raise
        
    finally:
        cur.close()
        conn.close()

def main():
    analyze_large_purchases()

if __name__ == "__main__":
    main()