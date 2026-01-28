#!/usr/bin/env python3
"""
Check which merchant deposit transactions already exist in December 2013.
"""

import os
import psycopg2

ACCOUNT = '903990106011'

def get_conn():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***')
    )

def main():
    conn = get_conn()
    cur = conn.cursor()
    
    # Get all Dec 2013 credits (deposits)
    cur.execute("""
        SELECT transaction_date, description, credit_amount
        FROM banking_transactions
        WHERE account_number = %s
        AND transaction_date >= '2013-12-01'
        AND transaction_date <= '2013-12-31'
        AND credit_amount > 0
        ORDER BY transaction_date, transaction_id
    """, (ACCOUNT,))
    
    deposits = cur.fetchall()
    
    print("\n" + "="*80)
    print("EXISTING DEPOSITS IN DECEMBER 2013")
    print("="*80)
    print(f"Total deposit transactions: {len(deposits)}")
    
    total = 0
    merchant_count = 0
    merchant_total = 0
    other_count = 0
    other_total = 0
    
    print("\n" + "-"*80)
    print(f"{'Date':<12} {'Amount':>12} {'Description':<50}")
    print("-"*80)
    
    for txn_date, description, amount in deposits:
        print(f"{txn_date.strftime('%Y-%m-%d'):<12} ${float(amount):>11,.2f} {description[:50]}")
        total += float(amount)
        
        if 'Merchant Deposit Credit' in description:
            merchant_count += 1
            merchant_total += float(amount)
        else:
            other_count += 1
            other_total += float(amount)
    
    print("-"*80)
    print(f"{'TOTAL':<12} ${total:>11,.2f}")
    
    print(f"\n{'='*80}")
    print("DEPOSIT BREAKDOWN")
    print("="*80)
    print(f"Merchant Deposit Credits: {merchant_count} transactions, ${merchant_total:,.2f}")
    print(f"Other Deposits: {other_count} transactions, ${other_total:,.2f}")
    print(f"Total: {len(deposits)} transactions, ${total:,.2f}")
    
    print(f"\nStatement shows total deposits: $70,463.81")
    print(f"Missing: ${70463.81 - total:,.2f}")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
