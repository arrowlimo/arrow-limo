#!/usr/bin/env python3
"""
Match Scotia deposits that have notes indicating partial funding from CIBC.
These are split transactions where part came from CIBC transfer and part was cash.
"""

import psycopg2
import os
from datetime import datetime, timedelta

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REDACTED***')
    )

def main():
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("\n" + "="*80)
    print("MATCH CIBC-SCOTIA SPLIT DEPOSIT TRANSACTIONS")
    print("="*80)
    
    # Known transactions from the Excel screenshot
    split_deposits = [
        {'date': '2012-07-16', 'scotia_amount': 400.00, 'cibc_partial': 400.00, 'description': 'DEPOSIT FROM CIBC ACCOUNT'},
        {'date': '2012-10-24', 'scotia_amount': 1700.00, 'cibc_partial': 1000.00, 'description': 'DEPOSIT $1000 FROM CIBC ACCOUNT'},
        {'date': '2012-10-26', 'scotia_amount': 1500.00, 'cibc_partial': 600.00, 'description': 'DEPOSIT $600 FROM cibc'},
        {'date': '2012-11-19', 'scotia_amount': 2000.00, 'cibc_partial': 1300.00, 'description': 'deposit $1300 from cibc'},
    ]
    
    print("\nSearching for Scotia deposits with CIBC notes and matching CIBC transactions...\n")
    
    matches_found = []
    
    for deposit in split_deposits:
        date = deposit['date']
        scotia_amt = deposit['scotia_amount']
        cibc_amt = deposit['cibc_partial']
        cash_amt = scotia_amt - cibc_amt
        desc = deposit['description']
        
        print(f"\n{'-'*80}")
        print(f"Date: {date}")
        print(f"Scotia Deposit: ${scotia_amt:,.2f}")
        print(f"  - From CIBC: ${cibc_amt:,.2f}")
        print(f"  - Cash: ${cash_amt:,.2f}")
        print(f"Description: {desc}")
        
        # Find Scotia banking transaction (credit/deposit)
        cur.execute("""
            SELECT transaction_id, transaction_date, description, credit_amount, debit_amount
            FROM banking_transactions
            WHERE account_number = '903990106011'
            AND transaction_date BETWEEN %s::date - interval '2 days' AND %s::date + interval '2 days'
            AND credit_amount = %s
            ORDER BY ABS(EXTRACT(EPOCH FROM (transaction_date::timestamp - %s::timestamp)))
            LIMIT 1
        """, (date, date, scotia_amt, date))
        
        scotia_tx = cur.fetchone()
        
        if scotia_tx:
            print(f"\n✓ Found Scotia deposit:")
            print(f"  TX ID: {scotia_tx[0]} | Date: {scotia_tx[1]} | Credit: ${scotia_tx[3]:,.2f}")
            print(f"  Description: {scotia_tx[2]}")
        else:
            print(f"\n✗ Scotia deposit not found in banking_transactions")
            continue
        
        # Find matching CIBC withdrawal (debit) around the same date
        date_start = f"{date}"
        date_end = f"{date}"
        cur.execute("""
            SELECT transaction_id, transaction_date, description, credit_amount, debit_amount
            FROM banking_transactions
            WHERE account_number = '0228362'
            AND transaction_date BETWEEN %s::date - interval '3 days' AND %s::date + interval '3 days'
            AND debit_amount = %s
            AND (LOWER(description) LIKE '%%transfer%%' OR LOWER(description) LIKE '%%withdrawal%%')
            ORDER BY ABS(EXTRACT(EPOCH FROM (transaction_date::timestamp - %s::timestamp)))
            LIMIT 3
        """, (date_start, date_end, cibc_amt, date))
        
        cibc_txs = cur.fetchall()
        
        if cibc_txs:
            print(f"\n✓ Found {len(cibc_txs)} potential CIBC withdrawal(s):")
            for i, tx in enumerate(cibc_txs, 1):
                print(f"  {i}. TX ID: {tx[0]} | Date: {tx[1]} | Debit: ${tx[4]:,.2f}")
                print(f"     Description: {tx[2]}")
                
                # Check if already linked
                cur.execute("""
                    SELECT COUNT(*) FROM banking_receipt_matching_ledger
                    WHERE banking_transaction_id = %s
                """, (tx[0],))
                
                linked_count = cur.fetchone()[0]
                if linked_count > 0:
                    print(f"     ⚠️  Already linked to {linked_count} receipt(s)")
            
            matches_found.append({
                'date': date,
                'scotia_tx_id': scotia_tx[0],
                'cibc_tx_id': cibc_txs[0][0],  # Best match
                'scotia_amount': scotia_amt,
                'cibc_amount': cibc_amt,
                'cash_amount': cash_amt,
                'description': desc
            })
        else:
            print(f"\n✗ No matching CIBC withdrawal found for ${cibc_amt:,.2f}")
    
    # Summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    print(f"Total split deposits identified: {len(split_deposits)}")
    print(f"Matches found (Scotia + CIBC): {len(matches_found)}")
    
    if matches_found:
        print("\nMatched Transactions:")
        print(f"{'Date':12} {'Scotia TX':>10} {'CIBC TX':>10} {'Scotia $':>12} {'CIBC $':>12} {'Cash $':>12}")
        print("-" * 80)
        for match in matches_found:
            print(f"{match['date']:12} {match['scotia_tx_id']:10} {match['cibc_tx_id']:10} "
                  f"${match['scotia_amount']:>10,.2f} ${match['cibc_amount']:>10,.2f} ${match['cash_amount']:>10,.2f}")
        
        print("\n💡 These transactions represent inter-account transfers (CIBC → Scotia)")
        print("   plus additional cash deposits. They should be linked to show the")
        print("   money flow and avoid double-counting in expense reports.")
    
    print("\n" + "="*80 + "\n")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
