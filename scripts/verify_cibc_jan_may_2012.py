#!/usr/bin/env python3
"""
CIBC Statement Jan-May 2012 Verification Against Screenshots
=============================================================
Verifies imported banking data matches original CIBC statements for:
- January 2012 through May 2012
- Account 00339-7461615 (canonical: 0228362)

Checks:
1. Monthly transaction counts
2. Opening/closing balances
3. Total debits and credits
4. Net change per month
5. Missing transactions
6. Duplicate entries
7. Amount discrepancies

Reports any import errors, wrong totals, missing withdrawals, etc.
"""

import psycopg2
import os
from decimal import Decimal
from collections import defaultdict

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        dbname=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REDACTED***')
    )

def get_canonical_account(cur, statement_format):
    """Find canonical account number using aliases"""
    cur.execute("""
        SELECT canonical_account_number
        FROM account_number_aliases
        WHERE statement_format = %s
        LIMIT 1
    """, (statement_format,))
    result = cur.fetchone()
    return result[0] if result else None

def get_monthly_summary(cur, account, year, month):
    """Get comprehensive monthly summary from database"""
    cur.execute("""
        SELECT 
            COUNT(*) as txn_count,
            MIN(transaction_date) as first_date,
            MAX(transaction_date) as last_date,
            SUM(CASE WHEN debit_amount > 0 THEN 1 ELSE 0 END) as debit_count,
            SUM(CASE WHEN credit_amount > 0 THEN 1 ELSE 0 END) as credit_count,
            SUM(debit_amount) as total_debits,
            SUM(credit_amount) as total_credits,
            SUM(credit_amount) - SUM(debit_amount) as net_change,
            MIN(balance) as min_balance,
            MAX(balance) as max_balance
        FROM banking_transactions
        WHERE account_number = %s
          AND EXTRACT(YEAR FROM transaction_date) = %s
          AND EXTRACT(MONTH FROM transaction_date) = %s
    """, (account, year, month))
    return cur.fetchone()

def get_daily_transactions(cur, account, date):
    """Get all transactions for a specific date"""
    cur.execute("""
        SELECT transaction_id, transaction_date, description,
               debit_amount, credit_amount, balance
        FROM banking_transactions
        WHERE account_number = %s
          AND transaction_date = %s
        ORDER BY transaction_id
    """, (account, date))
    return cur.fetchall()

def check_specific_amounts(cur, account, date, expected_amounts):
    """Check if specific amounts exist on a given date"""
    results = []
    for amount, txn_type, description_hint in expected_amounts:
        amt_col = "debit_amount" if txn_type == "debit" else "credit_amount"
        
        cur.execute(f"""
            SELECT transaction_id, transaction_date, description, 
                   debit_amount, credit_amount
            FROM banking_transactions
            WHERE account_number = %s
              AND transaction_date = %s
              AND {amt_col} > 0
              AND ABS({amt_col} - %s) < 0.01
            ORDER BY transaction_id
            LIMIT 1
        """, (account, date, Decimal(str(amount))))
        
        match = cur.fetchone()
        results.append({
            'amount': amount,
            'type': txn_type,
            'hint': description_hint,
            'found': match is not None,
            'match': match
        })
    
    return results

def main():
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("=" * 90)
    print("CIBC STATEMENT VERIFICATION: JAN-MAY 2012")
    print("Account: 00339-7461615 (CIBC Business Checking)")
    print("=" * 90)
    
    # Get canonical account
    canonical = get_canonical_account(cur, '00339-7461615')
    if not canonical:
        print("[FAIL] ERROR: Cannot find canonical account for 00339-7461615")
        return
    
    print(f"\n[OK] Using canonical account: {canonical}\n")
    
    # Define expected monthly totals from statements (to be filled in from screenshots)
    # Format: (year, month, expected_debits, expected_credits, expected_net_change, notes)
    expected_monthly = [
        (2012, 1, None, None, None, "January 2012 - awaiting screenshot data"),
        (2012, 2, None, None, None, "February 2012 - awaiting screenshot data"),
        (2012, 3, None, None, None, "March 2012 - awaiting screenshot data"),
        (2012, 4, None, None, None, "April 2012 - awaiting screenshot data"),
        (2012, 5, 56675.92, 46070.45, -10605.47, "May 2012 - Page 3 known data"),
    ]
    
    all_issues = []
    
    for year, month, exp_debits, exp_credits, exp_net, notes in expected_monthly:
        month_name = ['', 'January', 'February', 'March', 'April', 'May'][month]
        print(f"{'=' * 90}")
        print(f"📅 {month_name} {year}")
        print(f"{'=' * 90}")
        
        # Get actual data from database
        summary = get_monthly_summary(cur, canonical, year, month)
        if not summary:
            print(f"[FAIL] ERROR: No data returned for {month_name} {year}")
            continue
        
        (txn_count, first_date, last_date, debit_count, credit_count,
         total_debits, total_credits, net_change, min_bal, max_bal) = summary
        
        print(f"\n📊 Database Summary:")
        print(f"   Transaction count: {txn_count}")
        print(f"   Date range: {first_date} to {last_date}")
        print(f"   Debit transactions: {debit_count} (Total: ${total_debits:,.2f})")
        print(f"   Credit transactions: {credit_count} (Total: ${total_credits:,.2f})")
        print(f"   Net change: ${net_change:,.2f}")
        if min_bal is not None and max_bal is not None:
            print(f"   Balance range: ${min_bal:,.2f} to ${max_bal:,.2f}")
        
        # Compare with expected values if available
        if exp_debits is not None:
            print(f"\n🔍 Comparison with Statement:")
            
            debit_diff = abs(float(total_debits or 0) - float(exp_debits))
            credit_diff = abs(float(total_credits or 0) - float(exp_credits))
            net_diff = abs(float(net_change or 0) - float(exp_net))
            
            # Check debits
            if debit_diff < 0.01:
                print(f"   [OK] Debits match: ${total_debits:,.2f} = ${exp_debits:,.2f}")
            else:
                issue = f"{month_name} {year}: Debit mismatch - DB: ${total_debits:,.2f}, Expected: ${exp_debits:,.2f}, Diff: ${debit_diff:,.2f}"
                all_issues.append(issue)
                print(f"   [FAIL] Debits MISMATCH: ${total_debits:,.2f} vs ${exp_debits:,.2f} (Δ ${debit_diff:,.2f})")
            
            # Check credits
            if credit_diff < 0.01:
                print(f"   [OK] Credits match: ${total_credits:,.2f} = ${exp_credits:,.2f}")
            else:
                issue = f"{month_name} {year}: Credit mismatch - DB: ${total_credits:,.2f}, Expected: ${exp_credits:,.2f}, Diff: ${credit_diff:,.2f}"
                all_issues.append(issue)
                print(f"   [FAIL] Credits MISMATCH: ${total_credits:,.2f} vs ${exp_credits:,.2f} (Δ ${credit_diff:,.2f})")
            
            # Check net change
            if net_diff < 0.01:
                print(f"   [OK] Net change match: ${net_change:,.2f} = ${exp_net:,.2f}")
            else:
                issue = f"{month_name} {year}: Net change mismatch - DB: ${net_change:,.2f}, Expected: ${exp_net:,.2f}, Diff: ${net_diff:,.2f}"
                all_issues.append(issue)
                print(f"   [FAIL] Net change MISMATCH: ${net_change:,.2f} vs ${exp_net:,.2f} (Δ ${net_diff:,.2f})")
        else:
            print(f"\n[WARN] {notes}")
            print(f"   Please provide statement totals for verification")
        
        # Check for duplicates within this month
        cur.execute("""
            SELECT source_hash, COUNT(*) as dupe_count,
                   ARRAY_AGG(transaction_id ORDER BY transaction_id) as ids,
                   ARRAY_AGG(transaction_date ORDER BY transaction_id) as dates
            FROM banking_transactions
            WHERE account_number = %s
              AND EXTRACT(YEAR FROM transaction_date) = %s
              AND EXTRACT(MONTH FROM transaction_date) = %s
              AND source_hash IS NOT NULL
            GROUP BY source_hash
            HAVING COUNT(*) > 1
        """, (canonical, year, month))
        
        duplicates = cur.fetchall()
        if duplicates:
            print(f"\n[WARN] Found {len(duplicates)} duplicate transaction sets:")
            for hash_val, count, ids, dates in duplicates[:5]:  # Show first 5
                issue = f"{month_name} {year}: {count} duplicate transactions - IDs: {ids}"
                all_issues.append(issue)
                print(f"   🔄 {count}x duplicates: IDs {ids}, Dates {dates}")
        else:
            print(f"\n   [OK] No duplicates detected")
        
        # Check for zero-amount transactions (potential import errors)
        cur.execute("""
            SELECT COUNT(*)
            FROM banking_transactions
            WHERE account_number = %s
              AND EXTRACT(YEAR FROM transaction_date) = %s
              AND EXTRACT(MONTH FROM transaction_date) = %s
              AND debit_amount = 0
              AND credit_amount = 0
        """, (canonical, year, month))
        
        zero_count = cur.fetchone()[0]
        if zero_count > 0:
            issue = f"{month_name} {year}: {zero_count} zero-amount transactions (possible import error)"
            all_issues.append(issue)
            print(f"\n[WARN] Found {zero_count} zero-amount transactions (possible import errors)")
        
        # Check for NULL descriptions (data quality issue)
        cur.execute("""
            SELECT COUNT(*)
            FROM banking_transactions
            WHERE account_number = %s
              AND EXTRACT(YEAR FROM transaction_date) = %s
              AND EXTRACT(MONTH FROM transaction_date) = %s
              AND (description IS NULL OR description = '' OR description = 'nan')
        """, (canonical, year, month))
        
        null_desc_count = cur.fetchone()[0]
        if null_desc_count > 0:
            print(f"[WARN] Found {null_desc_count} transactions with missing descriptions")
        
        print()  # Blank line between months
    
    # Detailed daily verification for May 2012 (we have screenshot data)
    print(f"\n{'=' * 90}")
    print(f"🔍 DETAILED MAY 2012 VERIFICATION (Page 3 Items)")
    print(f"{'=' * 90}\n")
    
    # May 4, 2012 items from screenshot
    print("📅 May 4, 2012 - Expected Items:")
    may_4_items = [
        (37.50, 'debit', 'CENTEX/DEERPARK'),
        (94.65, 'debit', 'LIQUOR'),
        (80.52, 'debit', 'generic purchase'),
    ]
    
    may_4_results = check_specific_amounts(cur, canonical, '2012-05-04', may_4_items)
    may_4_found = sum(1 for r in may_4_results if r['found'])
    
    for result in may_4_results:
        if result['found']:
            print(f"   [OK] ${result['amount']:>7.2f} {result['type']:6} {result['hint']:30} - FOUND")
        else:
            issue = f"May 4, 2012: Missing ${result['amount']} {result['type']} ({result['hint']})"
            all_issues.append(issue)
            print(f"   [FAIL] ${result['amount']:>7.2f} {result['type']:6} {result['hint']:30} - MISSING")
    
    print(f"\n   Summary: {may_4_found}/{len(may_4_items)} items found\n")
    
    # May 7, 2012 items from screenshot
    print("📅 May 7, 2012 - Expected Items:")
    may_7_items = [
        (1756.20, 'debit', 'Cheque #'),
        (89.50, 'debit', 'CENTEX/DEERPARK'),
        (572.67, 'credit', 'DEPOSIT'),
        (78.73, 'debit', 'FUTURE SHOP'),
        (113.53, 'debit', 'HUSKY ELBOW'),
        (36.26, 'debit', 'FIVE GUYS'),
        (213.75, 'credit', 'CREDIT MEMO'),
        (200.00, 'credit', 'CREDIT MEMO'),
        (110.27, 'credit', 'CREDIT MEMO'),
        (101.14, 'debit', 'PRE AUTH DEBIT'),
    ]
    
    may_7_results = check_specific_amounts(cur, canonical, '2012-05-07', may_7_items)
    may_7_found = sum(1 for r in may_7_results if r['found'])
    
    for result in may_7_results:
        if result['found']:
            print(f"   [OK] ${result['amount']:>7.2f} {result['type']:6} {result['hint']:30} - FOUND")
        else:
            issue = f"May 7, 2012: Missing ${result['amount']} {result['type']} ({result['hint']})"
            all_issues.append(issue)
            print(f"   [FAIL] ${result['amount']:>7.2f} {result['type']:6} {result['hint']:30} - MISSING")
    
    print(f"\n   Summary: {may_7_found}/{len(may_7_items)} items found")
    
    # Check for May 7 transactions on May 8 (posting date lag)
    if may_7_found < len(may_7_items):
        print(f"\n   Checking May 8 for late-posting May 7 transactions...")
        may_7_on_8_results = check_specific_amounts(cur, canonical, '2012-05-08', may_7_items)
        may_7_on_8_found = sum(1 for r in may_7_on_8_results if r['found'])
        
        if may_7_on_8_found > 0:
            print(f"   ℹ️ Found {may_7_on_8_found} May 7 items that posted on May 8 (date lag)")
    
    # Overall summary
    print(f"\n{'=' * 90}")
    print(f"📊 VERIFICATION SUMMARY")
    print(f"{'=' * 90}\n")
    
    if all_issues:
        print(f"[FAIL] Found {len(all_issues)} issues:\n")
        for i, issue in enumerate(all_issues, 1):
            print(f"   {i}. {issue}")
    else:
        print(f"[OK] All verified data matches statements!")
        print(f"   No discrepancies found in available data")
    
    print(f"\n{'=' * 90}")
    print(f"[WARN] NEXT STEPS:")
    print(f"{'=' * 90}\n")
    print(f"1. Provide statement totals for Jan-Apr 2012 to complete verification")
    print(f"2. Review any identified discrepancies above")
    print(f"3. For missing May 7 items, check if they appear on:")
    print(f"   - Different dates (posting lag)")
    print(f"   - Different accounts (3648117 or 8314462)")
    print(f"   - Different import batches")
    print(f"\n4. Review duplicates with:")
    print(f"   SELECT * FROM v_banking_potential_duplicates WHERE")
    print(f"   transaction_ids && ARRAY[...]::INTEGER[];")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
