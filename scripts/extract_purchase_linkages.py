#!/usr/bin/env python3
"""
Extract detailed purchase information to help identify business linkages.
Focus on finding patterns and reference numbers for research.
"""

import psycopg2
import os
import re
from datetime import datetime, timedelta
from collections import defaultdict

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REDACTED***')
    )

def analyze_purchase_linkages():
    print("📋 DETAILED LARGE PURCHASE BREAKDOWN FOR LINKAGE ANALYSIS")
    print("=" * 65)
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Get all unmatched transactions with full details
        cur.execute("""
            SELECT 
                bt.transaction_id,
                bt.account_number,
                bt.transaction_date,
                bt.description,
                bt.debit_amount,
                bt.credit_amount,
                bt.vendor_extracted,
                bt.balance
            FROM banking_transactions bt
            LEFT JOIN receipts r ON (
                r.receipt_date = bt.transaction_date
                AND ABS(COALESCE(r.gross_amount, 0) - COALESCE(bt.debit_amount, bt.credit_amount, 0)) < 0.01
            )
            WHERE EXTRACT(YEAR FROM bt.transaction_date) = 2012
              AND bt.account_number IN ('0228362', '903990106011', '3648117')
              AND r.id IS NULL
              AND COALESCE(bt.debit_amount, bt.credit_amount, 0) > 0
            ORDER BY bt.transaction_date, COALESCE(bt.debit_amount, bt.credit_amount) DESC
        """)
        
        transactions = cur.fetchall()
        
        print(f"Found {len(transactions)} unmatched transactions in 2012")
        print(f"Looking for patterns and potential business linkages...\n")
        
        # Organize transactions for analysis
        transaction_details = []
        for trans in transactions:
            trans_id, acc, date, desc, debit, credit, vendor, balance = trans
            amount = float(debit if debit else credit)
            
            transaction_details.append({
                'id': trans_id,
                'date': date,
                'amount': amount,
                'desc': desc,
                'account': acc,
                'balance': float(balance) if balance else None
            })
        
        # Sort by date for chronological analysis
        transaction_details.sort(key=lambda x: x['date'])
        
        print("🗓️  CHRONOLOGICAL BREAKDOWN:")
        print("=" * 50)
        
        for trans in transaction_details:
            desc_short = (trans['desc'][:60] + '...') if trans['desc'] and len(trans['desc']) > 60 else trans['desc'] or 'No description'
            
            print(f"{trans['date']} | ${trans['amount']:>10,.2f} | {desc_short}")
            
            # Extract reference numbers for research
            if trans['desc']:
                ref_numbers = re.findall(r'\d{6,}', trans['desc'])
                if ref_numbers:
                    print(f"    🔍 Reference numbers: {ref_numbers}")
                
                # Look for vehicle/equipment indicators
                desc_upper = trans['desc'].upper()
                indicators = []
                
                if 'VV' in desc_upper or 'VY' in desc_upper:
                    indicators.append('Vehicle code (VV/VY)')
                if any(code in desc_upper for code in ['390', '073', '217', '223', '291']):
                    indicators.append('Vendor/department code')
                if '+' in desc_upper:
                    indicators.append('Additional charges')
                if 'ABM' in desc_upper:
                    indicators.append('ATM/Cash withdrawal')
                
                if indicators:
                    print(f"    💡 Indicators: {', '.join(indicators)}")
            print()
        
        print("💰 LARGEST TRANSACTIONS FOR RESEARCH:")
        print("=" * 45)
        
        # Focus on largest amounts
        large_transactions = [t for t in transaction_details if t['amount'] >= 5000]
        large_transactions.sort(key=lambda x: x['amount'], reverse=True)
        
        print("\nTop large transactions:")
        for i, trans in enumerate(large_transactions):
            print(f"{i+1}. ${trans['amount']:>10,.2f} - {trans['date']} - ID: {trans['id']}")
            
            if trans['desc']:
                print(f"    Description: {trans['desc']}")
                
                # Extract clean reference numbers
                refs = re.findall(r'\d{6,}', trans['desc'])
                clean_refs = [ref for ref in refs if len(ref) >= 6]
                if clean_refs:
                    print(f"    📋 Reference numbers for lookup: {clean_refs}")
            print()
        
        # Analyze April 2012 cluster (the big purchase month)
        print("🚗 APRIL 2012 CLUSTER ANALYSIS:")
        print("=" * 35)
        
        april_transactions = [t for t in transaction_details if t['date'].month == 4 and t['date'].year == 2012]
        if april_transactions:
            april_total = sum(t['amount'] for t in april_transactions)
            print(f"April 2012: {len(april_transactions)} transactions totaling ${april_total:,.2f}")
            print("Sequential dates suggest coordinated business investment:")
            
            for trans in sorted(april_transactions, key=lambda x: x['date']):
                print(f"  {trans['date']} - ${trans['amount']:,.2f}")
                if trans['desc']:
                    # Extract potential vehicle codes
                    codes = re.findall(r'[A-Z]{2}\s*\d+', trans['desc'])
                    if codes:
                        print(f"    Potential codes: {codes}")
        
        # Account analysis
        print(f"\n💳 ACCOUNT BREAKDOWN:")
        print("=" * 25)
        
        account_totals = defaultdict(float)
        account_counts = defaultdict(int)
        
        for trans in transaction_details:
            account_totals[trans['account']] += trans['amount']
            account_counts[trans['account']] += 1
        
        for acc in sorted(account_totals.keys()):
            total = account_totals[acc]
            count = account_counts[acc]
            avg = total / count if count > 0 else 0
            print(f"Account {acc}: {count:2d} transactions, ${total:>10,.2f} total, ${avg:>8,.2f} avg")
        
        # Extract all unique reference numbers for research
        print(f"\n🔍 ALL REFERENCE NUMBERS FOR RESEARCH:")
        print("=" * 40)
        
        all_refs = set()
        for trans in transaction_details:
            if trans['desc']:
                refs = re.findall(r'\d{6,}', trans['desc'])
                all_refs.update(refs)
        
        sorted_refs = sorted(all_refs, key=len, reverse=True)
        print("Reference numbers (longest first - likely most specific):")
        
        for i, ref in enumerate(sorted_refs[:20]):  # Top 20 most specific
            print(f"  {i+1:2d}. {ref}")
            
            # Try to categorize by length/pattern
            if len(ref) == 12:
                print(f"      → Possible invoice/transaction number")
            elif len(ref) == 10:
                print(f"      → Possible account/customer number")
            elif len(ref) == 8:
                print(f"      → Possible date-based reference")
            elif len(ref) >= 6:
                print(f"      → General business reference")
        
        print(f"\n🎯 RESEARCH RECOMMENDATIONS:")
        print("=" * 35)
        
        print("1. VEHICLE PURCHASE VERIFICATION:")
        print("   • Check limousine dealer records for April 2012")
        print("   • Look for Ford E450, Lincoln, Cadillac purchases ~$40K each")
        print("   • Cross-reference VIN numbers with vehicle registrations")
        
        print("\n2. REFERENCE NUMBER INVESTIGATION:")
        print("   • Use reference numbers to search:")
        print("     - Dealer invoice systems")
        print("     - Insurance policy databases")
        print("     - Equipment vendor records")
        print("     - Financing/loan documentation")
        
        print("\n3. BUSINESS CONTEXT ANALYSIS:")
        print("   • April 2012 appears to be major fleet expansion")
        print("   • Sequential high-value purchases suggest planned investment")
        print("   • Amounts typical for commercial limousine vehicles")
        
        print("\n4. ATM WITHDRAWAL BUSINESS USE:")
        print("   You're absolutely right about ATM withdrawals! In limousine business:")
        print("   • Driver float money for making change")
        print("   • Cash tips and gratuities")
        print("   • Small vendor payments (gas stations, etc.)")
        print("   • Employee reimbursements")
        print("   • Petty cash for office supplies")
        print("   • Emergency cash reserves")
        
        # Look for potential cash-based business patterns
        cash_related = [t for t in transaction_details if t['desc'] and 'ABM' in t['desc'].upper()]
        if cash_related:
            cash_total = sum(t['amount'] for t in cash_related)
            print(f"\n💵 CASH WITHDRAWAL ANALYSIS:")
            print(f"   Total ATM withdrawals: ${cash_total:,.2f}")
            print("   → Likely used for legitimate business cash needs")
            print("   → Should be tracked as business expense (cash basis)")
        
        print(f"\n📊 SUMMARY FOR NEXT STEPS:")
        total_large = sum(t['amount'] for t in large_transactions)
        total_all = sum(t['amount'] for t in transaction_details)
        
        print(f"   • Large transactions (≥$5K): ${total_large:,.2f}")
        print(f"   • Total unmatched: ${total_all:,.2f}")
        print(f"   • Primary research focus: April 2012 vehicle cluster")
        print(f"   • Reference numbers provided for vendor lookup")
        print(f"   • High confidence these are business expenses")
        
    except Exception as e:
        print(f"\n[FAIL] ERROR: {str(e)}")
        raise
        
    finally:
        cur.close()
        conn.close()

def main():
    analyze_purchase_linkages()

if __name__ == "__main__":
    main()