#!/usr/bin/env python3
"""
Verify 2012 banking transactions for accounts 1000, 1100, and RBC 9016.
Match banking transactions to receipts and identify missing receipt coverage.
"""

import psycopg2
import os
from datetime import datetime
from collections import defaultdict

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***')
    )

def verify_2012_banking_receipts():
    """Verify 2012 banking transactions match to receipts"""
    print("🏦 2012 BANKING TRANSACTION RECEIPT VERIFICATION")
    print("=" * 60)
    print("Target Accounts: 1000, 1100, RBC 9016")
    print("=" * 60)
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Step 1: Identify banking accounts and transaction patterns
        print("\n📊 STEP 1: Analyze banking account structure")
        
        cur.execute("""
            SELECT 
                account_number,
                COUNT(*) as transaction_count,
                SUM(COALESCE(debit_amount, 0)) as total_debits,
                SUM(COALESCE(credit_amount, 0)) as total_credits,
                MIN(transaction_date) as first_date,
                MAX(transaction_date) as last_date
            FROM banking_transactions 
            WHERE EXTRACT(YEAR FROM transaction_date) = 2012
              AND (account_number LIKE '%1000%' 
                   OR account_number LIKE '%1100%' 
                   OR account_number LIKE '%9016%'
                   OR account_number IN ('1000', '1100'))
            GROUP BY account_number
            ORDER BY transaction_count DESC
        """)
        
        banking_accounts = cur.fetchall()
        
        if not banking_accounts:
            print("[WARN]  No banking transactions found for target accounts in 2012")
            print("   Checking all available 2012 banking accounts...")
            
            cur.execute("""
                SELECT 
                    account_number,
                    COUNT(*) as transaction_count,
                    SUM(COALESCE(debit_amount, 0)) as total_debits,
                    SUM(COALESCE(credit_amount, 0)) as total_credits,
                    MIN(transaction_date) as first_date,
                    MAX(transaction_date) as last_date
                FROM banking_transactions 
                WHERE EXTRACT(YEAR FROM transaction_date) = 2012
                GROUP BY account_number
                ORDER BY transaction_count DESC
                LIMIT 10
            """)
            
            all_accounts = cur.fetchall()
            print(f"   Available 2012 banking accounts:")
            for acc, count, debits, credits, first_date, last_date in all_accounts:
                print(f"     {acc}: {count:,} transactions (${debits:,.2f} debits, ${credits:,.2f} credits)")
            
            if all_accounts:
                print(f"\n   Using top banking accounts for analysis...")
                banking_accounts = all_accounts[:3]  # Use top 3 accounts
        
        print(f"\n📋 BANKING ACCOUNTS ANALYSIS:")
        total_transactions = 0
        
        for acc, count, debits, credits, first_date, last_date in banking_accounts:
            total_transactions += count
            print(f"\n  Account: {acc}")
            print(f"    Transactions: {count:,}")
            print(f"    Debits: ${debits:,.2f}")
            print(f"    Credits: ${credits:,.2f}")
            print(f"    Date range: {first_date} to {last_date}")
        
        print(f"\n  Total transactions to verify: {total_transactions:,}")
        
        # Step 2: Match banking transactions to receipts
        print(f"\n🔍 STEP 2: Match banking transactions to receipts")
        
        target_accounts = [acc for acc, _, _, _, _, _ in banking_accounts]
        
        if not target_accounts:
            print("[FAIL] No target accounts found for verification")
            return
        
        # Build account filter
        account_filter = "(" + " OR ".join([f"account_number = '{acc}'" for acc in target_accounts]) + ")"
        
        cur.execute(f"""
            SELECT 
                bt.transaction_id,
                bt.account_number,
                bt.transaction_date,
                bt.description,
                bt.debit_amount,
                bt.credit_amount,
                bt.vendor_extracted,
                r.id as receipt_id,
                r.vendor_name as receipt_vendor,
                r.gross_amount as receipt_amount,
                r.source_system
            FROM banking_transactions bt
            LEFT JOIN receipts r ON (
                r.receipt_date = bt.transaction_date
                AND ABS(COALESCE(r.gross_amount, 0) - COALESCE(bt.debit_amount, bt.credit_amount, 0)) < 0.01
            )
            WHERE EXTRACT(YEAR FROM bt.transaction_date) = 2012
              AND {account_filter}
            ORDER BY bt.transaction_date DESC, bt.debit_amount DESC NULLS LAST
        """)
        
        matches = cur.fetchall()
        
        # Analyze matching results
        matched_transactions = []
        unmatched_transactions = []
        
        for match in matches:
            trans_id, acc, date, desc, debit, credit, vendor, receipt_id, receipt_vendor, receipt_amt, source = match
            amount = debit if debit else credit
            
            if receipt_id:
                matched_transactions.append(match)
            else:
                unmatched_transactions.append(match)
        
        # Step 3: Report matching results
        print(f"\n📊 STEP 3: Banking-Receipt matching results")
        
        print(f"\n[OK] MATCHED TRANSACTIONS: {len(matched_transactions):,}")
        if matched_transactions:
            matched_amount = sum(float(m[4] or m[5] or 0) for m in matched_transactions)
            print(f"   Total matched amount: ${matched_amount:,.2f}")
            
            # Show top matches by amount
            matched_sorted = sorted(matched_transactions, key=lambda x: float(x[4] or x[5] or 0), reverse=True)
            print(f"\n   Top 10 matched transactions:")
            print(f"   {'Date':<12} {'Amount':<10} {'Description':<40} {'Receipt':<15}")
            print(f"   {'-'*12} {'-'*10} {'-'*40} {'-'*15}")
            
            for match in matched_sorted[:10]:
                _, acc, date, desc, debit, credit, vendor, receipt_id, receipt_vendor, receipt_amt, source = match
                amount = debit if debit else credit
                desc_short = (desc[:37] + '...') if desc and len(desc) > 40 else desc or ''
                print(f"   {date} ${amount:<9.2f} {desc_short:<40} ID-{receipt_id}")
        
        # Step 4: Analyze unmatched transactions
        print(f"\n[FAIL] UNMATCHED TRANSACTIONS: {len(unmatched_transactions):,}")
        
        if unmatched_transactions:
            unmatched_amount = sum(float(m[4] or m[5] or 0) for m in unmatched_transactions)
            print(f"   Total unmatched amount: ${unmatched_amount:,.2f}")
            
            # Categorize unmatched transactions
            categories = defaultdict(list)
            
            for unmatch in unmatched_transactions:
                _, acc, date, desc, debit, credit, vendor, _, _, _, _ = unmatch
                amount = debit if debit else credit
                desc_lower = (desc or '').lower()
                
                if any(word in desc_lower for word in ['transfer', 'deposit', 'withdrawal']):
                    categories['internal_transfers'].append(unmatch)
                elif any(word in desc_lower for word in ['fee', 'charge', 'interest']):
                    categories['bank_fees'].append(unmatch)
                elif any(word in desc_lower for word in ['payment', 'purchase', 'pos']):
                    categories['missing_receipts'].append(unmatch)
                elif amount and amount > 1000:
                    categories['large_amounts'].append(unmatch)
                else:
                    categories['other'].append(unmatch)
            
            print(f"\n   📋 UNMATCHED TRANSACTION CATEGORIES:")
            for category, transactions in categories.items():
                if transactions:
                    cat_amount = sum(float(t[4] or t[5] or 0) for t in transactions)
                    print(f"     {category.replace('_', ' ').title()}: {len(transactions):,} transactions, ${cat_amount:,.2f}")
            
            # Show critical unmatched transactions (likely missing receipts)
            critical_unmatched = categories.get('missing_receipts', []) + categories.get('large_amounts', [])
            
            if critical_unmatched:
                critical_sorted = sorted(critical_unmatched, key=lambda x: float(x[4] or x[5] or 0), reverse=True)
                print(f"\n   🚨 TOP CRITICAL UNMATCHED (Missing Receipts?):")
                print(f"   {'Date':<12} {'Amount':<10} {'Account':<10} {'Description':<50}")
                print(f"   {'-'*12} {'-'*10} {'-'*10} {'-'*50}")
                
                for unmatch in critical_sorted[:20]:
                    _, acc, date, desc, debit, credit, vendor, _, _, _, _ = unmatch
                    amount = debit if debit else credit
                    desc_short = (desc[:47] + '...') if desc and len(desc) > 50 else desc or ''
                    print(f"   {date} ${amount:<9.2f} {acc:<10} {desc_short:<50}")
        
        # Step 5: Receipt coverage analysis
        print(f"\n📈 STEP 5: Receipt coverage analysis")
        
        cur.execute("""
            SELECT 
                COUNT(*) as total_receipts,
                SUM(gross_amount) as total_receipt_amount,
                COUNT(*) FILTER (WHERE source_system = 'QuickBooks-2012-Import') as qb_receipts,
                SUM(gross_amount) FILTER (WHERE source_system = 'QuickBooks-2012-Import') as qb_amount
            FROM receipts 
            WHERE EXTRACT(YEAR FROM receipt_date) = 2012
        """)
        
        total_receipts, total_receipt_amt, qb_receipts, qb_amount = cur.fetchone()
        
        print(f"\n   Total 2012 receipts: {total_receipts:,}")
        print(f"   Total receipt amount: ${total_receipt_amt:,.2f}")
        print(f"   QuickBooks receipts: {qb_receipts:,} (${qb_amount:,.2f})")
        print(f"   Other source receipts: {total_receipts - qb_receipts:,} (${total_receipt_amt - qb_amount:,.2f})")
        
        # Step 6: Summary and recommendations
        print(f"\n🎯 STEP 6: Summary and recommendations")
        
        match_rate = (len(matched_transactions) / len(matches) * 100) if matches else 0
        
        print(f"\n   📊 VERIFICATION SUMMARY:")
        print(f"     Banking transactions analyzed: {len(matches):,}")
        print(f"     Successfully matched: {len(matched_transactions):,} ({match_rate:.1f}%)")
        print(f"     Missing receipts: {len(unmatched_transactions):,}")
        
        if len(unmatched_transactions) > 0:
            unmatched_pct = (len(unmatched_transactions) / len(matches) * 100)
            print(f"     Unmatched rate: {unmatched_pct:.1f}%")
            
            if unmatched_pct > 20:
                print(f"\n   [WARN]  HIGH UNMATCHED RATE - Action required:")
                print(f"     - Review critical unmatched transactions above")
                print(f"     - Create receipts for legitimate business expenses")
                print(f"     - Investigate large amounts without receipts")
                print(f"     - Ensure all business expenses have proper documentation")
            elif unmatched_pct > 10:
                print(f"\n   [OK] MODERATE UNMATCHED RATE - Minor cleanup needed")
            else:
                print(f"\n   [OK] EXCELLENT MATCH RATE - Banking well documented")
        
        print(f"\n   🎯 NEXT STEPS:")
        print(f"     1. Review critical unmatched transactions")
        print(f"     2. Create missing receipts for business expenses")
        print(f"     3. Categorize internal transfers and fees appropriately")
        print(f"     4. Verify large amount transactions have proper documentation")
        
        # Generate detailed report if requested
        print(f"\n📄 Detailed reports available:")
        print(f"   - Run with --export-unmatched to export critical unmatched transactions")
        print(f"   - Run with --export-matched to export successfully matched transactions")
        
    except Exception as e:
        print(f"\n[FAIL] ERROR: {str(e)}")
        raise
        
    finally:
        cur.close()
        conn.close()

def main():
    """Main verification function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Verify 2012 banking transactions match to receipts')
    parser.add_argument('--export-unmatched', action='store_true', help='Export unmatched transactions to CSV')
    parser.add_argument('--export-matched', action='store_true', help='Export matched transactions to CSV')
    
    args = parser.parse_args()
    
    verify_2012_banking_receipts()
    
    if args.export_unmatched or args.export_matched:
        print(f"\n📤 Export functionality would be implemented here")

if __name__ == "__main__":
    main()