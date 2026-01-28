#!/usr/bin/env python3
"""
Find CIBC transactions around the dates of Scotia deposits with split notes.
Search broadly for any CIBC debits within date range.
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

def main():
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("\n" + "="*80)
    print("CIBC TRANSACTIONS AROUND SCOTIA SPLIT DEPOSIT DATES")
    print("="*80)
    
    # Known Scotia deposits with CIBC partial funding
    deposits = [
        {'date': '2012-07-15', 'cibc_amt': 400.00, 'scotia_tx': 63676},
        {'date': '2012-10-23', 'cibc_amt': 1000.00, 'scotia_tx': 64069},
        {'date': '2012-10-28', 'cibc_amt': 600.00, 'scotia_tx': 64078},
        {'date': '2012-11-18', 'cibc_amt': 1300.00, 'scotia_tx': 64164},
    ]
    
    for dep in deposits:
        date = dep['date']
        expected_amt = dep['cibc_amt']
        scotia_tx_id = dep['scotia_tx']
        
        print(f"\n{'-'*80}")
        print(f"Scotia TX {scotia_tx_id} on {date} - expecting CIBC debit of ${expected_amt:,.2f}")
        
        # Search for CIBC debits within ±5 days
        cur.execute("""
            SELECT transaction_id, transaction_date, description, debit_amount, credit_amount
            FROM banking_transactions
            WHERE account_number = '0228362'
            AND transaction_date BETWEEN %s::date - interval '5 days' AND %s::date + interval '5 days'
            AND debit_amount IS NOT NULL
            ORDER BY transaction_date, transaction_id
        """, (date, date))
        
        cibc_txs = cur.fetchall()
        
        print(f"\nFound {len(cibc_txs)} CIBC debits within ±5 days:")
        print(f"{'TX ID':>8} | {'Date':>10} | {'Debit':>12} | Description")
        print("-" * 80)
        
        for tx in cibc_txs:
            tx_id, tx_date, desc, debit, credit = tx
            marker = " ⭐" if abs(float(debit) - expected_amt) < 0.01 else ""
            print(f"{tx_id:8} | {tx_date} | ${float(debit):>10,.2f} | {desc[:50]}{marker}")
    
    print("\n" + "="*80 + "\n")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
