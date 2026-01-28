#!/usr/bin/env python3
"""
Search for cheques 215, 216, and 276 with wider criteria.
The banking statement shows these cheques cleared, so they must be in the database.
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
    print('SEARCHING FOR CHEQUES 215, 216, 276 IN BANKING TRANSACTIONS')
    print('=' * 80)
    print()

    # Search for cheque 215 - $150.00
    print('Cheque 215 - $150.00:')
    cur.execute('''
        SELECT transaction_id, transaction_date, description, debit_amount
        FROM banking_transactions
        WHERE description LIKE '%215%'
        AND debit_amount > 0
        ORDER BY transaction_date
    ''')
    
    results = cur.fetchall()
    if results:
        for r in results:
            print(f'  {r[0]}: {r[1]} | ${r[3]:,.2f} | {r[2][:70]}')
    else:
        print('  Not found by cheque number in description')
    
    print()
    
    # Search for cheque 216 - $100.00
    print('Cheque 216 - $100.00:')
    cur.execute('''
        SELECT transaction_id, transaction_date, description, debit_amount
        FROM banking_transactions
        WHERE description LIKE '%216%'
        AND debit_amount > 0
        ORDER BY transaction_date
    ''')
    
    results = cur.fetchall()
    if results:
        for r in results:
            print(f'  {r[0]}: {r[1]} | ${r[3]:,.2f} | {r[2][:70]}')
    else:
        print('  Not found by cheque number in description')
    
    print()
    
    # Search for cheque 276 - $1,050.00
    print('Cheque 276 - $1,050.00:')
    cur.execute('''
        SELECT transaction_id, transaction_date, description, debit_amount
        FROM banking_transactions
        WHERE description LIKE '%276%'
        AND debit_amount > 0
        ORDER BY transaction_date
    ''')
    
    results = cur.fetchall()
    if results:
        for r in results:
            print(f'  {r[0]}: {r[1]} | ${r[3]:,.2f} | {r[2][:70]}')
    else:
        print('  Not found by cheque number in description')
    
    print()
    print('=' * 80)
    print('SEARCHING BY AMOUNT IN MARCH-JULY 2012')
    print('=' * 80)
    print()
    
    # Search by amount for all three
    amounts = [
        (215, 150.00, '2012-03-01', '2012-04-30'),
        (216, 100.00, '2012-03-01', '2012-04-30'),
        (276, 1050.00, '2012-07-01', '2012-08-31'),
    ]
    
    for cheque_num, amount, start_date, end_date in amounts:
        print(f'Cheque {cheque_num} - ${amount:,.2f} between {start_date} and {end_date}:')
        cur.execute('''
            SELECT transaction_id, transaction_date, description, debit_amount
            FROM banking_transactions
            WHERE ABS(debit_amount - %s) < 0.01
            AND transaction_date BETWEEN %s AND %s
            ORDER BY transaction_date
        ''', (amount, start_date, end_date))
        
        results = cur.fetchall()
        if results:
            for r in results:
                print(f'  {r[0]}: {r[1]} | ${r[3]:,.2f} | {r[2][:70]}')
        else:
            print(f'  No {amount:,.2f} transactions found in this period')
        print()

    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
