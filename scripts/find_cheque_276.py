#!/usr/bin/env python3
"""
Search for cheque 276 using the exact reference from CIBC statement.
Statement shows: Cheque 276 000000017545393 | $1,050.00 | Jul 10
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
    print('SEARCHING FOR CHEQUE 276 FROM CIBC STATEMENT')
    print('Statement shows: Cheque 276 000000017545393 | $1,050.00 | Jul 10, 2012')
    print('=' * 80)
    print()

    # Search by reference number
    print('Searching by reference number 17545393:')
    cur.execute('''
        SELECT transaction_id, transaction_date, description, debit_amount
        FROM banking_transactions
        WHERE description LIKE '%17545393%'
        OR description LIKE '%1545393%'
        ORDER BY transaction_date
    ''')
    
    results = cur.fetchall()
    if results:
        for r in results:
            print(f'  {r[0]}: {r[1]} | ${r[3]:,.2f} | {r[2]}')
    else:
        print('  Not found by reference number')
    
    print()
    print('Searching by date and amount (Jul 10, 2012, $1,050):')
    cur.execute('''
        SELECT transaction_id, transaction_date, description, debit_amount
        FROM banking_transactions
        WHERE transaction_date = '2012-07-10'
        AND debit_amount BETWEEN 1049 AND 1051
    ''')
    
    results = cur.fetchall()
    if results:
        for r in results:
            print(f'  {r[0]}: {r[1]} | ${r[3]:,.2f} | {r[2]}')
            print(f'  [OK] FOUND! This matches cheque 276')
    else:
        print('  Not found by date and amount')
        print()
        print('  Checking nearby dates:')
        cur.execute('''
            SELECT transaction_id, transaction_date, description, debit_amount
            FROM banking_transactions
            WHERE transaction_date BETWEEN '2012-07-08' AND '2012-07-13'
            AND debit_amount BETWEEN 1049 AND 1051
            ORDER BY transaction_date
        ''')
        nearby = cur.fetchall()
        if nearby:
            for r in nearby:
                print(f'    {r[0]}: {r[1]} | ${r[3]:,.2f} | {r[2]}')
        else:
            print('    No $1,050 transactions found Jul 8-13')

    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
