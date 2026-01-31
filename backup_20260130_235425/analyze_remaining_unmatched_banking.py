#!/usr/bin/env python3
"""
Analyze remaining unmatched banking transactions (non-vehicle) for fees, NSF, and other items
"""

import psycopg2
import os
from collections import defaultdict

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REDACTED***')
    )

def analyze_remaining_unmatched():
    print("🏦 ANALYZING REMAINING UNMATCHED BANKING TRANSACTIONS - 2012")
    print("=" * 65)
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Get all unmatched transactions (excluding the vehicle ones we just created receipts for)
        cur.execute("""
            SELECT 
                bt.transaction_id,
                bt.transaction_date,
                bt.account_number,
                bt.description,
                bt.debit_amount,
                bt.credit_amount,
                bt.balance
            FROM banking_transactions bt
            LEFT JOIN receipts r ON (
                r.receipt_date = bt.transaction_date 
                AND ABS(COALESCE(r.gross_amount, 0) - COALESCE(bt.debit_amount, bt.credit_amount, 0)) < 1.00
            )
            WHERE EXTRACT(YEAR FROM bt.transaction_date) = 2012
              AND bt.account_number IN ('0228362', '903990106011', '3648117')
              AND r.id IS NULL  -- No matching receipt found
              AND NOT (
                  bt.account_number = '3648117' 
                  AND bt.debit_amount IS NOT NULL 
                  AND bt.debit_amount >= 1000
                  AND UPPER(COALESCE(bt.description, '')) LIKE '%PURCHASE%'
              )  -- Exclude vehicle purchases we already handled
            ORDER BY COALESCE(bt.debit_amount, bt.credit_amount, 0) DESC
        """)
        
        remaining_unmatched = cur.fetchall()
        
        print(f"Found {len(remaining_unmatched)} remaining unmatched transactions (excluding vehicles)")
        print()
        
        # Categorize the transactions by type
        categories = {
            'bank_fees': [],
            'nsf_insufficient_funds': [],
            'service_charges': [],
            'interest_charges': [],
            'transfers': [],
            'deposits': [],
            'withdrawals': [],
            'credit_memos': [],
            'debit_memos': [],
            'other': []
        }
        
        total_unmatched = 0
        
        for trans_id, date, account, desc, debit, credit, balance in remaining_unmatched:
            amount = credit if credit else debit
            if amount:
                total_unmatched += float(amount)
            
            desc_upper = str(desc).upper() if desc else ''
            
            # Categorize based on description patterns
            if any(term in desc_upper for term in ['NSF', 'INSUFFICIENT', 'NON-SUFFICIENT', 'RETURNED']):
                categories['nsf_insufficient_funds'].append((trans_id, date, account, desc, debit, credit, balance))
            elif any(term in desc_upper for term in ['SERVICE CHARGE', 'MONTHLY FEE', 'MAINTENANCE FEE', 'ACCOUNT FEE']):
                categories['service_charges'].append((trans_id, date, account, desc, debit, credit, balance))
            elif any(term in desc_upper for term in ['INTEREST', 'OVERDRAFT']):
                categories['interest_charges'].append((trans_id, date, account, desc, debit, credit, balance))
            elif any(term in desc_upper for term in ['TRANSFER', 'TSFR', 'ETSF', 'ETF']):
                categories['transfers'].append((trans_id, date, account, desc, debit, credit, balance))
            elif credit and credit > 0:
                categories['deposits'].append((trans_id, date, account, desc, debit, credit, balance))
            elif any(term in desc_upper for term in ['WITHDRAWAL', 'ABM', 'ATM']):
                categories['withdrawals'].append((trans_id, date, account, desc, debit, credit, balance))
            elif any(term in desc_upper for term in ['CREDIT MEMO', 'CR MEMO']):
                categories['credit_memos'].append((trans_id, date, account, desc, debit, credit, balance))
            elif any(term in desc_upper for term in ['DEBIT MEMO', 'DR MEMO']):
                categories['debit_memos'].append((trans_id, date, account, desc, debit, credit, balance))
            else:
                categories['other'].append((trans_id, date, account, desc, debit, credit, balance))
        
        print(f"💰 TOTAL REMAINING UNMATCHED: ${total_unmatched:,.2f}")
        print()
        
        # Analyze each category
        for category, transactions in categories.items():
            if not transactions:
                continue
                
            category_total = sum(float(credit if credit else debit) for _, _, _, _, debit, credit, _ in transactions)
            category_name = category.replace('_', ' ').title()
            
            print(f"📊 {category_name.upper()} ({len(transactions)} transactions, ${category_total:,.2f}):")
            print("=" * (len(category_name) + 25))
            
            # Show details for each category
            if category == 'nsf_insufficient_funds':
                print("NSF/Insufficient Funds Analysis:")
                nsf_pairs = []
                
                for trans_id, date, account, desc, debit, credit, balance in transactions:
                    amount = credit if credit else debit
                    trans_type = "REVERSAL" if credit else "NSF CHARGE"
                    print(f"  {date} | Account {account} | {trans_type} | ${amount:,.2f}")
                    print(f"    {desc}")
                    
                    # Look for NSF patterns (original charge + reversal + re-attempt)
                    if 'NSF' in str(desc).upper() or 'INSUFFICIENT' in str(desc).upper():
                        print(f"    *** NSF EVENT - Needs tracking ***")
                    print()
                
                if transactions:
                    print(f"  Status: [FAIL] CRITICAL - NSF events need proper expense tracking")
                    print(f"  Action: Create NSF fee receipts and track customer impacts")
                
            elif category == 'service_charges':
                print("Service Charges Analysis:")
                for trans_id, date, account, desc, debit, credit, balance in transactions:
                    amount = credit if credit else debit
                    print(f"  {date} | Account {account} | ${amount:,.2f}")
                    print(f"    {desc}")
                    print()
                
                if transactions:
                    print(f"  Status: [WARN] MISSING RECEIPTS - Bank fees are business expenses")
                    print(f"  Action: Create bank fee receipts for tax deduction")
                
            elif category == 'interest_charges':
                print("Interest/Overdraft Charges Analysis:")
                for trans_id, date, account, desc, debit, credit, balance in transactions:
                    amount = credit if credit else debit
                    print(f"  {date} | Account {account} | ${amount:,.2f}")
                    print(f"    {desc}")
                    print()
                
                if transactions:
                    print(f"  Status: [WARN] MISSING RECEIPTS - Interest charges are business expenses")
                    print(f"  Action: Create interest expense receipts")
                
            elif category == 'transfers':
                print("Transfer Analysis:")
                transfer_amounts = defaultdict(list)
                
                for trans_id, date, account, desc, debit, credit, balance in transactions:
                    amount = credit if credit else debit
                    transfer_amounts[date].append((amount, account, desc))
                    print(f"  {date} | Account {account} | ${amount:,.2f}")
                    print(f"    {desc}")
                    print()
                
                # Check for matching transfer pairs
                print(f"  Transfer Pair Analysis:")
                for date, amounts in transfer_amounts.items():
                    if len(amounts) > 1:
                        print(f"    {date}: Multiple transfers - Check for matching pairs")
                
                if transactions:
                    print(f"  Status: [OK] INTERNAL TRANSFERS - May not need receipts")
                    print(f"  Action: Verify transfers balance and are internal movements")
                
            elif category == 'deposits':
                print("Unmatched Deposits Analysis:")
                large_deposits = []
                small_deposits = []
                
                for trans_id, date, account, desc, debit, credit, balance in transactions:
                    if float(credit) >= 1000:
                        large_deposits.append((trans_id, date, account, desc, debit, credit, balance))
                    else:
                        small_deposits.append((trans_id, date, account, desc, debit, credit, balance))
                
                if large_deposits:
                    print(f"  Large Deposits (≥$1,000):")
                    for trans_id, date, account, desc, debit, credit, balance in large_deposits:
                        print(f"    {date} | Account {account} | ${credit:,.2f}")
                        print(f"      {desc}")
                        print(f"      *** REVENUE SOURCE - Needs classification ***")
                        print()
                
                if small_deposits:
                    print(f"  Small Deposits (<$1,000): {len(small_deposits)} totaling ${sum(float(c) for _, _, _, _, _, c, _ in small_deposits):,.2f}")
                
                if transactions:
                    print(f"  Status: [FAIL] CRITICAL - Unmatched deposits may be missing revenue")
                    print(f"  Action: Classify as revenue, refunds, or other income sources")
                
            elif category == 'withdrawals':
                print("Withdrawal Analysis:")
                for trans_id, date, account, desc, debit, credit, balance in transactions:
                    amount = debit
                    print(f"  {date} | Account {account} | ${amount:,.2f}")
                    print(f"    {desc}")
                    if float(amount) > 500:
                        print(f"    *** LARGE WITHDRAWAL - Verify business purpose ***")
                    print()
                
                if transactions:
                    print(f"  Status: [WARN] NEED REVIEW - Cash withdrawals need business justification")
                    print(f"  Action: Verify business purpose and create expense receipts if applicable")
                
            else:  # other, credit_memos, debit_memos
                print(f"{category_name} Analysis:")
                for trans_id, date, account, desc, debit, credit, balance in transactions[:10]:  # Show first 10
                    amount = credit if credit else debit
                    trans_type = "CREDIT" if credit else "DEBIT"
                    print(f"  {date} | Account {account} | {trans_type} ${amount:,.2f}")
                    print(f"    {desc}")
                    print()
                
                if len(transactions) > 10:
                    print(f"  ... and {len(transactions) - 10} more entries")
                
                if transactions:
                    print(f"  Status: [WARN] NEED INDIVIDUAL REVIEW")
                    print(f"  Action: Analyze each transaction for business relevance")
            
            print()
        
        # Summary and recommendations
        print("🎯 UNMATCHED BANKING SUMMARY:")
        print("=" * 29)
        print()
        
        priority_items = []
        
        for category, transactions in categories.items():
            if transactions:
                category_total = sum(float(credit if credit else debit) for _, _, _, _, debit, credit, _ in transactions)
                category_name = category.replace('_', ' ').title()
                
                if category == 'nsf_insufficient_funds':
                    priority = "HIGH"
                    action = "Track NSF fees as business expenses"
                elif category in ['service_charges', 'interest_charges']:
                    priority = "HIGH" 
                    action = "Create bank fee receipts for tax deduction"
                elif category == 'deposits':
                    priority = "CRITICAL"
                    action = "Classify unmatched deposits as revenue"
                elif category == 'withdrawals':
                    priority = "MEDIUM"
                    action = "Verify business purpose of cash withdrawals"
                elif category == 'transfers':
                    priority = "LOW"
                    action = "Verify internal transfer balancing"
                else:
                    priority = "MEDIUM"
                    action = "Individual transaction review"
                
                priority_items.append((priority, category_name, len(transactions), category_total, action))
        
        # Sort by priority
        priority_order = {'CRITICAL': 0, 'HIGH': 1, 'MEDIUM': 2, 'LOW': 3}
        priority_items.sort(key=lambda x: (priority_order.get(x[0], 4), -x[3]))
        
        for priority, category, count, total, action in priority_items:
            print(f"{priority} PRIORITY - {category}:")
            print(f"  Transactions: {count}")
            print(f"  Amount: ${total:,.2f}")
            print(f"  Action: {action}")
            print()
        
        # Check current receipt coverage for these categories  
        cur.execute("""
            SELECT 
                category,
                COUNT(*) as receipt_count,
                SUM(gross_amount) as total_amount
            FROM receipts 
            WHERE EXTRACT(YEAR FROM receipt_date) = 2012
              AND category IN ('Bank Fees', 'Interest Expense', 'NSF Fees', 'Service Charges')
            GROUP BY category
        """)
        
        existing_coverage = cur.fetchall()
        
        if existing_coverage:
            print("📊 CURRENT BANKING EXPENSE COVERAGE:")
            print("=" * 35)
            for category, count, total in existing_coverage:
                print(f"  {category}: {count} receipts, ${float(total):,.2f}")
        else:
            print("[FAIL] NO EXISTING BANKING EXPENSE RECEIPTS FOUND")
            print("   Banking fees, NSF charges, and interest expenses are not being tracked!")
        
        print()
        
        print("📋 IMMEDIATE ACTIONS NEEDED:")
        print("=" * 26)
        print("1. 🏦 CREATE BANK FEE RECEIPTS:")
        print("   - Service charges, monthly fees, maintenance fees")
        print("   - NSF charges and insufficient fund fees")  
        print("   - Interest and overdraft charges")
        print("   - All are legitimate business expense deductions")
        print()
        
        print("2. 💰 CLASSIFY UNMATCHED DEPOSITS:")
        print("   - Large deposits may be missing revenue")
        print("   - Small deposits may be refunds or corrections")
        print("   - Need proper revenue recognition")
        print()
        
        print("3. 💵 VERIFY CASH WITHDRAWALS:")
        print("   - Large withdrawals need business justification")
        print("   - May be petty cash, owner draws, or business expenses")
        print("   - Create receipts for legitimate business use")
        print()
        
        print("4. 🔄 VALIDATE TRANSFERS:")
        print("   - Ensure internal transfers balance")
        print("   - No receipts needed for genuine internal movements")
        print("   - Flag any unexplained transfer differences")
        
        print()
        print(f"📈 TOTAL DOCUMENTATION GAP: ${total_unmatched:,.2f}")
        print("This represents untracked banking activity that could impact:")
        print("- Tax deduction opportunities (bank fees, interest)")
        print("- Revenue recognition (unmatched deposits)")
        print("- Cash flow analysis (unexplained movements)")
        print("- CRA audit compliance (missing documentation)")
        
    except Exception as e:
        print(f"\n[FAIL] ERROR: {str(e)}")
        raise
        
    finally:
        cur.close()
        conn.close()

def main():
    analyze_remaining_unmatched()

if __name__ == "__main__":
    main()