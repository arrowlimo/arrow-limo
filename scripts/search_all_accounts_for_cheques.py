#!/usr/bin/env python3
"""
Search for cheques 215, 216, 276 across ALL accounts with 2012 data.
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
    print('SEARCHING FOR CHEQUES 215, 216, 276 ACROSS ALL ACCOUNTS')
    print('=' * 80)
    print()

    accounts = ['0228362', '3648117', '903990106011']
    target_cheques = [
        ('215', 150.00, '2012-03-15', '2012-03-25'),
        ('216', 100.00, '2012-03-15', '2012-03-25'),
        ('276', 1050.00, '2012-07-08', '2012-07-13'),
    ]
    
    for cheque_num, amount, start_date, end_date in target_cheques:
        print(f'CHEQUE {cheque_num} - ${amount:,.2f} ({start_date} to {end_date})')
        print('-' * 80)
        
        for account in accounts:
            # Search by cheque number in description
            cur.execute('''
                SELECT transaction_id, transaction_date, description, debit_amount, account_number
                FROM banking_transactions
                WHERE account_number = %s
                AND description LIKE %s
                AND debit_amount > 0
                ORDER BY transaction_date
            ''', (account, f'%{cheque_num}%'))
            
            results = cur.fetchall()
            if results:
                print(f'\n  Account {account} - Found by cheque number:')
                for r in results:
                    print(f'    {r[0]}: {r[1]} | ${r[3]:,.2f} | {r[2][:60]}')
            
            # Search by amount and date range
            cur.execute('''
                SELECT transaction_id, transaction_date, description, debit_amount, account_number
                FROM banking_transactions
                WHERE account_number = %s
                AND transaction_date BETWEEN %s AND %s
                AND ABS(debit_amount - %s) < 0.01
                ORDER BY transaction_date
            ''', (account, start_date, end_date, amount))
            
            results = cur.fetchall()
            if results:
                print(f'\n  Account {account} - Found by amount and date:')
                for r in results:
                    print(f'    {r[0]}: {r[1]} | ${r[3]:,.2f} | {r[2][:60]}')
        
        print()

    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
