#!/usr/bin/env python3
"""
Analyze CIBC banking accounts in the database.
Shows account numbers, transaction counts, date ranges, and totals.
"""

import psycopg2
import os
from decimal import Decimal

def get_db_connection():
    """Get database connection using environment variables."""
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REDACTED***')
    )

def analyze_cibc_accounts():
    """Analyze all CIBC accounts in banking_transactions."""
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("=" * 120)
    print(" " * 40 + "CIBC ACCOUNTS IN DATABASE")
    print("=" * 120)
    print()
    
    # Get all accounts except Scotia
    cur.execute("""
        SELECT 
            account_number,
            COUNT(*) as txn_count,
            MIN(transaction_date) as first_date,
            MAX(transaction_date) as last_date,
            SUM(debit_amount) as total_debits,
            SUM(credit_amount) as total_credits,
            COUNT(CASE WHEN debit_amount > 0 THEN 1 END) as debit_count,
            COUNT(CASE WHEN credit_amount > 0 THEN 1 END) as credit_count
        FROM banking_transactions
        WHERE account_number != '903990106011'
        GROUP BY account_number
        ORDER BY account_number
    """)
    
    accounts = cur.fetchall()
    
    if not accounts:
        print("No CIBC accounts found in database.")
        print("(Only Scotia account 903990106011 exists)")
        cur.close()
        conn.close()
        return
    
    print(f"{'Account':<20} {'Transactions':>12} {'First Date':<12} {'Last Date':<12} {'Total Debits':>15} {'Total Credits':>15}")
    print("-" * 120)
    
    total_transactions = 0
    total_debits = Decimal('0')
    total_credits = Decimal('0')
    
    for row in accounts:
        acct, txn_count, first_date, last_date, debits, credits, debit_cnt, credit_cnt = row
        total_transactions += txn_count
        total_debits += Decimal(str(debits or 0))
        total_credits += Decimal(str(credits or 0))
        
        print(f"{acct:<20} {txn_count:>12} {str(first_date):<12} {str(last_date):<12} ${debits or 0:>13,.2f} ${credits or 0:>13,.2f}")
        print(f"{'':20} {'':12} {'':12} {'':12} {debit_cnt:>6} debits    {credit_cnt:>6} credits")
        print()
    
    print("-" * 120)
    print(f"{'TOTAL':<20} {total_transactions:>12} {'':12} {'':12} ${total_debits:>13,.2f} ${total_credits:>13,.2f}")
    print()
    print(f"Total CIBC accounts: {len(accounts)}")
    print()
    
    # Show year breakdown for each account
    print("=" * 120)
    print(" " * 35 + "YEAR BREAKDOWN BY ACCOUNT")
    print("=" * 120)
    print()
    
    for acct_row in accounts:
        acct = acct_row[0]
        print(f"\nAccount: {acct}")
        print(f"{'Year':>6} {'Transactions':>12} {'Debits':>15} {'Credits':>15}")
        print("-" * 50)
        
        cur.execute("""
            SELECT 
                EXTRACT(YEAR FROM transaction_date) as year,
                COUNT(*) as txn_count,
                SUM(debit_amount) as total_debits,
                SUM(credit_amount) as total_credits
            FROM banking_transactions
            WHERE account_number = %s
            GROUP BY EXTRACT(YEAR FROM transaction_date)
            ORDER BY year
        """, (acct,))
        
        year_rows = cur.fetchall()
        for year, txn_count, debits, credits in year_rows:
            print(f"{int(year):>6} {txn_count:>12} ${debits or 0:>13,.2f} ${credits or 0:>13,.2f}")
        print()
    
    # Check for receipts linked to CIBC transactions
    print("=" * 120)
    print(" " * 30 + "RECEIPT MATCHING STATUS (CIBC)")
    print("=" * 120)
    print()
    
    for acct_row in accounts:
        acct = acct_row[0]
        
        cur.execute("""
            SELECT 
                COUNT(*) as total,
                COUNT(CASE WHEN receipt_id IS NOT NULL THEN 1 END) as matched
            FROM banking_transactions
            WHERE account_number = %s
              AND debit_amount > 0
        """, (acct,))
        
        total, matched = cur.fetchone()
        pct = (matched / total * 100) if total > 0 else 0
        
        print(f"Account {acct}:")
        print(f"  Debit transactions: {total}")
        print(f"  Matched to receipts: {matched} ({pct:.1f}%)")
        print()
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    analyze_cibc_accounts()
