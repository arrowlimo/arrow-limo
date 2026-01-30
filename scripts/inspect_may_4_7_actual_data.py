#!/usr/bin/env python3
"""
Inspect what transactions ARE actually in the database for May 4 & 7, 2012
===========================================================================
"""

import psycopg2
import os

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        dbname=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REDACTED***')
    )

def main():
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("=" * 100)
    print("ACTUAL DATABASE TRANSACTIONS: MAY 4 & 7, 2012 (Account 0228362)")
    print("=" * 100)
    
    for date in ['2012-05-04', '2012-05-07']:
        print(f"\n📅 {date}")
        print("-" * 100)
        
        cur.execute("""
            SELECT transaction_id, transaction_date, description,
                   debit_amount, credit_amount, balance
            FROM banking_transactions
            WHERE account_number = '0228362'
              AND transaction_date = %s
            ORDER BY transaction_id
        """, (date,))
        
        rows = cur.fetchall()
        
        if rows:
            print(f"Found {len(rows)} transactions:")
            for txn_id, txn_date, desc, debit, credit, bal in rows:
                desc_str = (desc or 'NULL')[:50]
                print(f"  ID {txn_id:6} | {txn_date} | Debit: ${debit or 0:>10.2f} | Credit: ${credit or 0:>10.2f} | Bal: ${bal or 0:>10.2f}")
                print(f"           Description: {desc_str}")
        else:
            print(f"[FAIL] NO transactions found")
    
    # Also check if transactions exist in other accounts
    print(f"\n\n{'=' * 100}")
    print("CHECKING OTHER CIBC ACCOUNTS FOR MAY 4 & 7, 2012")
    print("=" * 100)
    
    for account in ['3648117', '8314462', '1010', '1615']:
        for date in ['2012-05-04', '2012-05-07']:
            cur.execute("""
                SELECT COUNT(*), SUM(debit_amount), SUM(credit_amount)
                FROM banking_transactions
                WHERE account_number = %s
                  AND transaction_date = %s
            """, (account, date))
            
            count, debits, credits = cur.fetchone()
            if count > 0:
                print(f"\n📌 Account {account}, {date}: {count} transactions, ${debits or 0:.2f} debits, ${credits or 0:.2f} credits")
    
    # Check for transactions in date range across ALL accounts
    print(f"\n\n{'=' * 100}")
    print("ALL ACCOUNTS: MAY 4-7, 2012 SUMMARY")
    print("=" * 100)
    
    cur.execute("""
        SELECT account_number, 
               COUNT(*) as txn_count,
               SUM(debit_amount) as total_debits,
               SUM(credit_amount) as total_credits
        FROM banking_transactions
        WHERE transaction_date BETWEEN '2012-05-04' AND '2012-05-07'
        GROUP BY account_number
        ORDER BY account_number
    """)
    
    for acct, count, debits, credits in cur.fetchall():
        print(f"Account {acct:12} | {count:3} txns | Debits: ${debits or 0:>10.2f} | Credits: ${credits or 0:>10.2f}")
    
    # Check if maybe description matching is the issue - look for partial matches
    print(f"\n\n{'=' * 100}")
    print("SEARCHING FOR PARTIAL DESCRIPTION MATCHES (May 2012)")
    print("=" * 100)
    
    keywords = ['CENTEX', 'LIQUOR', 'FUTURE SHOP', 'HUSKY', 'FIVE GUYS', 'CREDIT MEMO', 'PRE AUTH']
    
    for keyword in keywords:
        cur.execute("""
            SELECT transaction_date, description, debit_amount, credit_amount
            FROM banking_transactions
            WHERE account_number = '0228362'
              AND transaction_date BETWEEN '2012-05-01' AND '2012-05-31'
              AND UPPER(description) LIKE %s
            LIMIT 5
        """, (f'%{keyword}%',))
        
        matches = cur.fetchall()
        if matches:
            print(f"\n🔍 Keyword: '{keyword}' - {len(matches)} matches")
            for date, desc, debit, credit in matches:
                print(f"   {date} | ${debit or 0:>7.2f} debit | ${credit or 0:>7.2f} credit | {(desc or 'NULL')[:60]}")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
