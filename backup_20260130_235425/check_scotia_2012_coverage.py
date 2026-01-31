#!/usr/bin/env python3
"""
Check Scotia Bank 2012 coverage in database.
Verify if we have similar QuickBooks vs Statement issues as 2013.
"""

import os
import psycopg2

ACCOUNT = '903990106011'

def get_conn():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REDACTED***')
    )

def main():
    conn = get_conn()
    cur = conn.cursor()
    
    print("\n" + "="*80)
    print("SCOTIA BANK 2012 DATABASE COVERAGE CHECK")
    print("="*80)
    
    # Check if we have any Scotia 2012 data
    cur.execute("""
        SELECT 
            EXTRACT(MONTH FROM transaction_date) as month,
            COUNT(*) as txn_count,
            SUM(debit_amount) as total_debits,
            SUM(credit_amount) as total_credits,
            MIN(transaction_date) as first_date,
            MAX(transaction_date) as last_date
        FROM banking_transactions
        WHERE account_number = %s
        AND EXTRACT(YEAR FROM transaction_date) = 2012
        GROUP BY EXTRACT(MONTH FROM transaction_date)
        ORDER BY month
    """, (ACCOUNT,))
    
    rows = cur.fetchall()
    
    if not rows:
        print("\n❌ NO SCOTIA BANK 2012 DATA FOUND IN DATABASE")
        print("\nThis confirms the issue - we likely only imported CIBC 2012.")
        print("Scotia Bank 2012 needs to be imported from bank statements.")
    else:
        print(f"\n✅ Found Scotia Bank 2012 data: {len(rows)} months")
        print("\nMonthly breakdown:")
        print(f"{'Month':<10} {'Txns':<8} {'Debits':<15} {'Credits':<15} {'Date Range'}")
        print("-" * 80)
        
        total_txns = 0
        total_debits = 0
        total_credits = 0
        
        for month, count, debits, credits, first, last in rows:
            month_name = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 
                         'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'][int(month)]
            debits_val = float(debits) if debits else 0
            credits_val = float(credits) if credits else 0
            
            print(f"{month_name:<10} {count:<8} ${debits_val:>12,.2f} ${credits_val:>12,.2f} {first} to {last}")
            
            total_txns += count
            total_debits += debits_val
            total_credits += credits_val
        
        print("-" * 80)
        print(f"{'TOTAL':<10} {total_txns:<8} ${total_debits:>12,.2f} ${total_credits:>12,.2f}")
    
    # Check for description patterns
    if rows:
        print("\n" + "="*80)
        print("TRANSACTION SOURCE ANALYSIS")
        print("="*80)
        
        cur.execute("""
            SELECT description, COUNT(*) as count
            FROM banking_transactions
            WHERE account_number = %s
            AND EXTRACT(YEAR FROM transaction_date) = 2012
            GROUP BY description
            ORDER BY count DESC
            LIMIT 20
        """, (ACCOUNT,))
        
        print("\nTop 20 transaction descriptions:")
        for desc, count in cur.fetchall():
            print(f"{count:>4} {desc[:70]}")
        
        # Check for QuickBooks patterns (Cheque dd)
        cur.execute("""
            SELECT COUNT(*) as qb_count
            FROM banking_transactions
            WHERE account_number = %s
            AND EXTRACT(YEAR FROM transaction_date) = 2012
            AND description LIKE '%%Cheque dd%%'
        """, (ACCOUNT,))
        
        qb_result = cur.fetchone()
        qb_count = qb_result[0] if qb_result else 0
        
        cur.execute("""
            SELECT COUNT(*) as stmt_count
            FROM banking_transactions
            WHERE account_number = %s
            AND EXTRACT(YEAR FROM transaction_date) = 2012
            AND description LIKE '%%Merchant Deposit%%'
        """, (ACCOUNT,))
        
        merchant_result = cur.fetchone()
        merchant_count = merchant_result[0] if merchant_result else 0
        
        print("\n" + "="*80)
        print("SOURCE IDENTIFICATION")
        print("="*80)
        print(f"QuickBooks patterns (Cheque dd): {qb_count}")
        print(f"Bank statement patterns (Merchant Deposit): {merchant_count}")
        
        if qb_count > merchant_count:
            print("\n⚠️  WARNING: More QuickBooks patterns than bank statement patterns")
            print("This suggests 2012 Scotia data may be from QuickBooks, not statements")
            print("QuickBooks is INCOMPLETE - missing merchant deposits and many transactions")
        else:
            print("\n✅ Appears to be from bank statements (has merchant deposits)")
    
    cur.close()
    conn.close()
    
    print("\n" + "="*80)

if __name__ == '__main__':
    main()
