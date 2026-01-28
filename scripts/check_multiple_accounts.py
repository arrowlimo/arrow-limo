#!/usr/bin/env python3
"""
Check for multiple CIBC accounts in the banking system.
"""

import psycopg2

def main():
    conn = psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REMOVED***'
    )
    cur = conn.cursor()

    print('=' * 80)
    print('CHECKING FOR MULTIPLE CIBC ACCOUNTS')
    print('=' * 80)
    print()

    # Check distinct account numbers
    print('Account numbers in banking_transactions:')
    cur.execute('''
        SELECT DISTINCT account_number, COUNT(*) as transactions
        FROM banking_transactions
        WHERE account_number IS NOT NULL
        GROUP BY account_number
        ORDER BY account_number
    ''')
    
    accounts = cur.fetchall()
    for acc in accounts:
        print(f'  Account {acc[0]}: {acc[1]:,} transactions')
    
    print()
    print(f'Total distinct accounts: {len(accounts)}')
    print()
    
    # Check 2012 data by account
    print('=' * 80)
    print('2012 TRANSACTIONS BY ACCOUNT')
    print('=' * 80)
    print()
    
    cur.execute('''
        SELECT 
            account_number,
            COUNT(*) as transactions,
            MIN(transaction_date) as first_date,
            MAX(transaction_date) as last_date,
            SUM(CASE WHEN debit_amount > 0 THEN 1 ELSE 0 END) as debits,
            SUM(CASE WHEN credit_amount > 0 THEN 1 ELSE 0 END) as credits
        FROM banking_transactions
        WHERE EXTRACT(YEAR FROM transaction_date) = 2012
        AND account_number IS NOT NULL
        GROUP BY account_number
        ORDER BY account_number
    ''')
    
    for row in cur.fetchall():
        print(f'Account {row[0]}:')
        print(f'  Transactions: {row[1]:,}')
        print(f'  Date range: {row[2]} to {row[3]}')
        print(f'  Debits: {row[4]:,} | Credits: {row[5]:,}')
        print()
    
    # Check for NULL account_number transactions
    cur.execute('''
        SELECT COUNT(*), MIN(transaction_date), MAX(transaction_date)
        FROM banking_transactions
        WHERE account_number IS NULL
        AND EXTRACT(YEAR FROM transaction_date) = 2012
    ''')
    
    null_count, null_min, null_max = cur.fetchone()
    if null_count > 0:
        print(f'Transactions with NULL account_number in 2012: {null_count:,}')
        print(f'  Date range: {null_min} to {null_max}')
        print()
    
    # Check cheque register linkage by account
    print('=' * 80)
    print('CHEQUE REGISTER LINKED TO WHICH ACCOUNTS?')
    print('=' * 80)
    print()
    
    cur.execute('''
        SELECT 
            bt.account_number,
            COUNT(*) as cheques,
            COUNT(DISTINCT CASE WHEN cr.cheque_number IN ('215', '216', '276') 
                  THEN cr.cheque_number END) as target_cheques
        FROM cheque_register cr
        LEFT JOIN banking_transactions bt ON cr.banking_transaction_id = bt.transaction_id
        WHERE cr.banking_transaction_id IS NOT NULL
        GROUP BY bt.account_number
        ORDER BY bt.account_number
    ''')
    
    for row in cur.fetchall():
        acc = row[0] if row[0] else 'NULL'
        print(f'Account {acc}: {row[1]} cheques linked')
        if row[2] > 0:
            print(f'  Includes {row[2]} of our target cheques (215, 216, 276)')
    
    print()
    
    # Check if target cheques are in a different account
    print('=' * 80)
    print('TARGET CHEQUES 215, 216, 276 - CURRENT STATUS')
    print('=' * 80)
    print()
    
    for cheque_num in ['215', '216', '276']:
        cur.execute('''
            SELECT 
                cr.cheque_number,
                cr.amount,
                cr.payee,
                cr.banking_transaction_id,
                bt.transaction_date,
                bt.account_number,
                bt.description
            FROM cheque_register cr
            LEFT JOIN banking_transactions bt ON cr.banking_transaction_id = bt.transaction_id
            WHERE cr.cheque_number = %s
        ''', (cheque_num,))
        
        result = cur.fetchone()
        if result:
            print(f'Cheque {result[0]}: ${result[1]:,.2f} | {result[2]}')
            if result[3]:
                print(f'  Linked to: Bank {result[3]} | {result[4]} | Account {result[5]}')
                print(f'  Description: {result[6][:60]}')
            else:
                print(f'  Status: UNLINKED (no banking_transaction_id)')
        print()

    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
