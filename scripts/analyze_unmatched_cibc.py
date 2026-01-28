#!/usr/bin/env python3
"""
Analyze unmatched CIBC transactions to identify patterns and opportunities.
Focus on largest gaps and easiest wins.
"""

import psycopg2
import os
from collections import defaultdict
from decimal import Decimal

def get_db_connection():
    """Get database connection using environment variables."""
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***')
    )

def analyze_unmatched_cibc():
    """Analyze unmatched CIBC transactions."""
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("=" * 120)
    print(" " * 35 + "UNMATCHED CIBC TRANSACTIONS ANALYSIS")
    print("=" * 120)
    print()
    
    # Get summary by account
    accounts = ['0228362', '1010', '1615', '3648117', '8314462']
    
    for acct in accounts:
        print(f"\n{'=' * 120}")
        print(f" Account: {acct}")
        print(f"{'=' * 120}\n")
        
        # Overall stats
        cur.execute("""
            SELECT 
                COUNT(CASE WHEN debit_amount > 0 AND receipt_id IS NULL THEN 1 END) as unmatched_debits,
                SUM(CASE WHEN debit_amount > 0 AND receipt_id IS NULL THEN debit_amount ELSE 0 END) as unmatched_debit_amt,
                COUNT(CASE WHEN credit_amount > 0 AND receipt_id IS NULL THEN 1 END) as unmatched_credits,
                SUM(CASE WHEN credit_amount > 0 AND receipt_id IS NULL THEN credit_amount ELSE 0 END) as unmatched_credit_amt
            FROM banking_transactions
            WHERE account_number = %s
        """, (acct,))
        
        unmatched_debits, unmatched_debit_amt, unmatched_credits, unmatched_credit_amt = cur.fetchone()
        
        print(f"Unmatched Debits:  {unmatched_debits} transactions, ${unmatched_debit_amt or 0:,.2f}")
        print(f"Unmatched Credits: {unmatched_credits} transactions, ${unmatched_credit_amt or 0:,.2f}")
        print()
        
        if unmatched_debits == 0 and unmatched_credits == 0:
            print("✓ All transactions matched!")
            continue
        
        # Year breakdown
        print(f"{'Year':>6} {'Unmatched Debits':>17} {'Unmatched Credits':>17}")
        print("-" * 50)
        
        cur.execute("""
            SELECT 
                EXTRACT(YEAR FROM transaction_date) as year,
                COUNT(CASE WHEN debit_amount > 0 AND receipt_id IS NULL THEN 1 END) as unmatched_debits,
                COUNT(CASE WHEN credit_amount > 0 AND receipt_id IS NULL THEN 1 END) as unmatched_credits
            FROM banking_transactions
            WHERE account_number = %s
            GROUP BY EXTRACT(YEAR FROM transaction_date)
            HAVING COUNT(CASE WHEN debit_amount > 0 AND receipt_id IS NULL THEN 1 END) > 0
                OR COUNT(CASE WHEN credit_amount > 0 AND receipt_id IS NULL THEN 1 END) > 0
            ORDER BY year
        """, (acct,))
        
        year_rows = cur.fetchall()
        for year, debits, credits in year_rows:
            print(f"{int(year):>6} {debits:>17} {credits:>17}")
        print()
        
        # Sample unmatched debits
        if unmatched_debits > 0:
            print(f"Sample Unmatched Debits (showing first 10):")
            print(f"{'Date':<12} {'Amount':>12} {'Description':<60}")
            print("-" * 90)
            
            cur.execute("""
                SELECT transaction_date, debit_amount, description
                FROM banking_transactions
                WHERE account_number = %s
                  AND debit_amount > 0
                  AND receipt_id IS NULL
                ORDER BY transaction_date
                LIMIT 10
            """, (acct,))
            
            samples = cur.fetchall()
            for date, amt, desc in samples:
                print(f"{date} ${amt:>11,.2f} {desc[:60]}")
            print()
        
        # Sample unmatched credits
        if unmatched_credits > 0:
            print(f"Sample Unmatched Credits (showing first 10):")
            print(f"{'Date':<12} {'Amount':>12} {'Description':<60}")
            print("-" * 90)
            
            cur.execute("""
                SELECT transaction_date, credit_amount, description
                FROM banking_transactions
                WHERE account_number = %s
                  AND credit_amount > 0
                  AND receipt_id IS NULL
                ORDER BY transaction_date
                LIMIT 10
            """, (acct,))
            
            samples = cur.fetchall()
            for date, amt, desc in samples:
                print(f"{date} ${amt:>11,.2f} {desc[:60]}")
            print()
    
    # Summary recommendations
    print("\n" + "=" * 120)
    print(" " * 40 + "RECOMMENDATIONS")
    print("=" * 120)
    print()
    
    print("Priority Order for CIBC Account Cleanup:")
    print()
    print("1. Account 1010 (2013 only):")
    print("   - 974 unmatched debits (0% matched)")
    print("   - Single year makes it straightforward")
    print("   - Apply Scotia 2012 smart matching techniques")
    print()
    print("2. Account 0228362:")
    print("   - 1,057 unmatched debits (81.4% already matched)")
    print("   - Multi-year (2012-2025) - focus on gaps")
    print("   - Good baseline match rate to build on")
    print()
    print("3. Account 3648117:")
    print("   - 1,451 unmatched debits (84.2% already matched)")
    print("   - Multi-year (2012-2025)")
    print("   - High match rate suggests good data quality")
    print()
    print("4. Accounts 1615 and 8314462:")
    print("   - Already well-matched (87.5% and 88.8%)")
    print("   - Small remaining gaps - low priority")
    print()
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    analyze_unmatched_cibc()
