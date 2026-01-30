#!/usr/bin/env python3
"""
Verify Scotia Bank December 2013 statement coverage against database.
Compare actual bank statement transactions to what's already imported.
"""

import os
import psycopg2
from datetime import datetime

ACCOUNT = '903990106011'

def get_conn():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REDACTED***')
    )

def main():
    print("\n" + "="*80)
    print("SCOTIA BANK DECEMBER 2013 STATEMENT COVERAGE VERIFICATION")
    print("="*80)
    
    conn = get_conn()
    cur = conn.cursor()
    
    # Get all December 2013 transactions from database
    cur.execute("""
        SELECT 
            transaction_date,
            description,
            debit_amount,
            credit_amount,
            source_hash
        FROM banking_transactions
        WHERE account_number = %s
        AND transaction_date >= '2013-12-01'
        AND transaction_date <= '2013-12-31'
        ORDER BY transaction_date, transaction_id
    """, (ACCOUNT,))
    
    db_transactions = cur.fetchall()
    
    print(f"\nDatabase has {len(db_transactions)} transactions for December 2013")
    
    # Calculate totals
    total_debits = sum(float(t[2] or 0) for t in db_transactions)
    total_credits = sum(float(t[3] or 0) for t in db_transactions)
    
    print(f"Total debits: ${total_debits:,.2f}")
    print(f"Total credits: ${total_credits:,.2f}")
    print(f"Net change: ${total_credits - total_debits:+,.2f}")
    
    # Expected from statement
    statement_debits = 59578.37
    statement_credits = 70463.81
    
    print(f"\n{'='*80}")
    print("COMPARISON TO BANK STATEMENT")
    print(f"{'='*80}")
    print(f"Statement debits: ${statement_debits:,.2f}")
    print(f"Statement credits: ${statement_credits:,.2f}")
    print(f"Statement net: ${statement_credits - statement_debits:+,.2f}")
    
    debit_diff = abs(total_debits - statement_debits)
    credit_diff = abs(total_credits - statement_credits)
    
    print(f"\n{'='*80}")
    print("VARIANCE ANALYSIS")
    print(f"{'='*80}")
    print(f"Debit variance: ${debit_diff:,.2f} ({debit_diff/statement_debits*100:.2f}%)")
    print(f"Credit variance: ${credit_diff:,.2f} ({credit_diff/statement_credits*100:.2f}%)")
    
    if debit_diff < 1.00 and credit_diff < 1.00:
        print("\n✅ PERFECT MATCH - All statement transactions are in database!")
    elif debit_diff < 10.00 and credit_diff < 10.00:
        print("\n✅ EXCELLENT - Minor variance within acceptable range (<$10)")
    elif debit_diff < 100.00 and credit_diff < 100.00:
        print("\n⚠️ GOOD - Some variance detected (<$100)")
    else:
        print("\n❌ SIGNIFICANT VARIANCE - Review needed")
    
    # Show transaction breakdown by date
    print(f"\n{'='*80}")
    print("DAILY TRANSACTION BREAKDOWN")
    print(f"{'='*80}")
    
    cur.execute("""
        SELECT 
            transaction_date,
            COUNT(*) as txn_count,
            SUM(debit_amount) as daily_debits,
            SUM(credit_amount) as daily_credits
        FROM banking_transactions
        WHERE account_number = %s
        AND transaction_date >= '2013-12-01'
        AND transaction_date <= '2013-12-31'
        GROUP BY transaction_date
        ORDER BY transaction_date
    """, (ACCOUNT,))
    
    daily_summary = cur.fetchall()
    
    print(f"\n{'Date':<15} {'Count':<8} {'Debits':>15} {'Credits':>15} {'Net':>15}")
    print("-" * 80)
    
    for date, count, debits, credits in daily_summary:
        net = float(credits or 0) - float(debits or 0)
        print(f"{date.strftime('%Y-%m-%d'):<15} {count:<8} ${float(debits or 0):>13,.2f} ${float(credits or 0):>13,.2f} ${net:>13,.2f}")
    
    # Key transactions check
    print(f"\n{'='*80}")
    print("KEY TRANSACTION VERIFICATION")
    print(f"{'='*80}")
    
    # Check for major deposits
    cur.execute("""
        SELECT transaction_date, description, credit_amount
        FROM banking_transactions
        WHERE account_number = %s
        AND transaction_date >= '2013-12-01'
        AND transaction_date <= '2013-12-31'
        AND credit_amount > 1000
        ORDER BY credit_amount DESC
        LIMIT 10
    """, (ACCOUNT,))
    
    large_deposits = cur.fetchall()
    
    print(f"\nLarge deposits (>$1,000):")
    for date, desc, amount in large_deposits:
        print(f"  {date}: {desc[:50]:<50} ${float(amount):>10,.2f}")
    
    # Check for major withdrawals
    cur.execute("""
        SELECT transaction_date, description, debit_amount
        FROM banking_transactions
        WHERE account_number = %s
        AND transaction_date >= '2013-12-01'
        AND transaction_date <= '2013-12-31'
        AND debit_amount > 1000
        ORDER BY debit_amount DESC
        LIMIT 10
    """, (ACCOUNT,))
    
    large_debits = cur.fetchall()
    
    print(f"\nLarge withdrawals (>$1,000):")
    for date, desc, amount in large_debits:
        print(f"  {date}: {desc[:50]:<50} ${float(amount):>10,.2f}")
    
    cur.close()
    conn.close()
    
    print("\n" + "="*80)

if __name__ == '__main__':
    main()
