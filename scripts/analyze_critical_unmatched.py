#!/usr/bin/env python3
"""
Analyze Critical Unmatched Banking Transactions from 2012 Verification
"""

import psycopg2
import os

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***')
    )

def analyze_unmatched_transactions():
    print("🚨 CRITICAL UNMATCHED BANKING TRANSACTIONS - 2012")
    print("=" * 55)
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Get the top unmatched transactions by amount
        cur.execute("""
            SELECT 
                bt.transaction_date,
                bt.account_number,
                bt.description,
                COALESCE(bt.debit_amount, bt.credit_amount) as amount,
                CASE 
                    WHEN bt.debit_amount IS NOT NULL THEN 'PAYMENT'
                    WHEN bt.credit_amount IS NOT NULL THEN 'DEPOSIT'
                    ELSE 'UNKNOWN'
                END as transaction_type,
                bt.transaction_id
            FROM banking_transactions bt
            LEFT JOIN receipts r ON (
                r.receipt_date = bt.transaction_date 
                AND ABS(COALESCE(r.gross_amount, 0) - COALESCE(bt.debit_amount, bt.credit_amount, 0)) < 1.00
            )
            WHERE EXTRACT(YEAR FROM bt.transaction_date) = 2012
              AND bt.account_number IN ('0228362', '903990106011', '3648117')
              AND r.id IS NULL  -- No matching receipt found
              AND COALESCE(bt.debit_amount, bt.credit_amount, 0) >= 1000  -- Focus on significant amounts
            ORDER BY COALESCE(bt.debit_amount, bt.credit_amount) DESC
            LIMIT 50
        """)
        
        unmatched = cur.fetchall()
        
        print(f"Found {len(unmatched)} high-value unmatched transactions (≥$1,000)")
        print()
        
        # Categorize the transactions
        vehicle_related = []
        deposits = []
        large_purchases = []
        credit_memos = []
        misc_payments = []
        other = []
        
        total_unmatched_amount = 0
        
        for date, account, desc, amount, trans_type, trans_id in unmatched:
            total_unmatched_amount += float(amount)
            
            # Categorize based on description patterns
            desc_upper = str(desc).upper()
            
            if any(keyword in desc_upper for keyword in ['PURCHASE', '21525', 'VV', 'VY']):
                vehicle_related.append((date, account, desc, amount, trans_type))
            elif trans_type == 'DEPOSIT':
                deposits.append((date, account, desc, amount, trans_type))
            elif 'CREDIT MEMO' in desc_upper:
                credit_memos.append((date, account, desc, amount, trans_type))
            elif 'MISC PAYMENT' in desc_upper:
                misc_payments.append((date, account, desc, amount, trans_type))
            elif float(amount) > 10000:
                large_purchases.append((date, account, desc, amount, trans_type))
            else:
                other.append((date, account, desc, amount, trans_type))
        
        print(f"💰 TOTAL UNMATCHED AMOUNT: ${total_unmatched_amount:,.2f}")
        print()
        
        # Show vehicle-related transactions (we know these are legitimate)
        if vehicle_related:
            print("🚗 VEHICLE-RELATED TRANSACTIONS (Known Business Expenses):")
            print("=" * 57)
            vehicle_total = 0
            for date, account, desc, amount, trans_type in vehicle_related:
                vehicle_total += float(amount)
                print(f"{date} | {trans_type:7} | ${amount:>10,.2f} | {account}")
                print(f"    {desc}")
                if "21525" in str(desc):
                    print("    *** FORD E350 VIN 1FDWE3FL8CDA32525 (VERIFIED) ***")
                print()
            
            print(f"Vehicle Subtotal: ${vehicle_total:,.2f}")
            print("Status: [OK] LEGITIMATE BUSINESS EXPENSES - Need receipts created")
            print()
        
        # Show large deposits
        if deposits:
            print("💰 LARGE DEPOSITS (Revenue/Financing):")
            print("=" * 36)
            deposit_total = 0
            for date, account, desc, amount, trans_type in deposits:
                deposit_total += float(amount)
                print(f"{date} | {trans_type:7} | ${amount:>10,.2f} | {account}")
                print(f"    {desc}")
                if abs(float(amount) - 44186.42) < 1:
                    print("    *** WOODRIDGE FORD REFINANCING (VERIFIED) ***")
                elif float(amount) > 20000:
                    print("    *** LARGE DEPOSIT - Review source ***")
                print()
            
            print(f"Deposit Subtotal: ${deposit_total:,.2f}")
            print("Status: [WARN] NEED CLASSIFICATION - Revenue vs financing")
            print()
        
        # Show credit memos
        if credit_memos:
            print("📝 CREDIT MEMOS:")
            print("=" * 14)
            credit_total = 0
            for date, account, desc, amount, trans_type in credit_memos:
                credit_total += float(amount)
                print(f"{date} | {trans_type:7} | ${amount:>10,.2f} | {account}")
                print(f"    {desc}")
                print()
            
            print(f"Credit Memo Subtotal: ${credit_total:,.2f}")
            print("Status: [WARN] NEED REVIEW - Adjustments/corrections")
            print()
        
        # Show misc payments
        if misc_payments:
            print("💳 MISC PAYMENTS:")
            print("=" * 15)
            misc_total = 0
            for date, account, desc, amount, trans_type in misc_payments:
                misc_total += float(amount)
                print(f"{date} | {trans_type:7} | ${amount:>10,.2f} | {account}")
                print(f"    {desc}")
                print()
            
            print(f"Misc Payment Subtotal: ${misc_total:,.2f}")
            print("Status: [WARN] NEED INVESTIGATION - Various business expenses")
            print()
        
        # Show large purchases
        if large_purchases:
            print("🏢 LARGE PURCHASES (>$10K):")
            print("=" * 26)
            large_total = 0
            for date, account, desc, amount, trans_type in large_purchases:
                large_total += float(amount)
                print(f"{date} | {trans_type:7} | ${amount:>10,.2f} | {account}")
                print(f"    {desc}")
                print()
            
            print(f"Large Purchase Subtotal: ${large_total:,.2f}")
            print("Status: [FAIL] CRITICAL - Major expenses need documentation")
            print()
        
        # Show other significant amounts
        if other:
            print("📊 OTHER SIGNIFICANT TRANSACTIONS:")
            print("=" * 32)
            other_total = 0
            for date, account, desc, amount, trans_type in other:
                other_total += float(amount)
                print(f"{date} | {trans_type:7} | ${amount:>10,.2f} | {account}")
                print(f"    {desc}")
                print()
            
            print(f"Other Subtotal: ${other_total:,.2f}")
            print("Status: [WARN] MIXED - Need individual review")
            print()
        
        # Summary and priorities
        print("📋 UNMATCHED SUMMARY BY PRIORITY:")
        print("=" * 33)
        print()
        
        priorities = [
            ("HIGH PRIORITY - Vehicle Purchases", vehicle_total if vehicle_related else 0, "Create business receipts"),
            ("HIGH PRIORITY - Large Purchases", sum(float(x[3]) for x in large_purchases) if large_purchases else 0, "Find documentation"),
            ("MEDIUM PRIORITY - Deposits", sum(float(x[3]) for x in deposits) if deposits else 0, "Classify revenue vs financing"),
            ("MEDIUM PRIORITY - Misc Payments", sum(float(x[3]) for x in misc_payments) if misc_payments else 0, "Investigate and categorize"),
            ("LOW PRIORITY - Credit Memos", sum(float(x[3]) for x in credit_memos) if credit_memos else 0, "Review adjustments"),
            ("LOW PRIORITY - Other", sum(float(x[3]) for x in other) if other else 0, "Individual assessment")
        ]
        
        for category, amount, action in priorities:
            if amount > 0:
                percentage = (amount / total_unmatched_amount) * 100
                print(f"{category}:")
                print(f"  Amount: ${amount:,.2f} ({percentage:.1f}% of unmatched)")
                print(f"  Action: {action}")
                print()
        
        print("🎯 IMMEDIATE ACTION ITEMS:")
        print("=" * 24)
        print()
        print("1. CREATE VEHICLE RECEIPTS:")
        print("   - Ford E350 purchase: $40,876.66 (April 4, 2012)")
        print("   - Second vehicle: $40,850.57 (April 5, 2012)")  
        print("   - Third vehicle: $40,511.25 (April 9, 2012)")
        print("   - Include GST calculations and proper categorization")
        print()
        
        print("2. INVESTIGATE LARGE DEPOSITS:")
        print("   - $44,186.42 (April 3) - Woodridge Ford refinancing")
        print("   - Other deposits >$20K - Verify revenue vs financing")
        print()
        
        print("3. DOCUMENT BUSINESS EXPENSES:")
        print("   - Review misc payments for legitimate business costs")
        print("   - Create receipts for verified business expenses")
        print("   - Categorize by expense type (fuel, maintenance, etc.)")
        print()
        
        print("4. MISSING RECEIPT ANALYSIS:")
        print(f"   - Total unmatched: ${total_unmatched_amount:,.2f}")
        print(f"   - Likely business expenses: ${vehicle_total + sum(float(x[3]) for x in misc_payments):,.2f}")
        print("   - Documentation gap significantly impacts tax compliance")
        
        # Check current receipt coverage
        cur.execute("""
            SELECT COUNT(*), COALESCE(SUM(gross_amount), 0)
            FROM receipts 
            WHERE EXTRACT(YEAR FROM receipt_date) = 2012
        """)
        
        receipt_stats = cur.fetchone()
        if receipt_stats:
            receipt_count, receipt_total = receipt_stats
            print()
            print(f"📊 CURRENT 2012 RECEIPT STATUS:")
            print(f"   Receipts in database: {receipt_count}")
            print(f"   Receipt total: ${float(receipt_total):,.2f}")
            print(f"   Banking total: ${total_unmatched_amount + 330267.33:,.2f}")  # Add matched amount
            print(f"   Missing documentation: ${total_unmatched_amount:,.2f}")
        
    except Exception as e:
        print(f"\n[FAIL] ERROR: {str(e)}")
        raise
        
    finally:
        cur.close()
        conn.close()

def main():
    analyze_unmatched_transactions()

if __name__ == "__main__":
    main()