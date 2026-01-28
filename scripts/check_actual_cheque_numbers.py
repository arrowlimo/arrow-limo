#!/usr/bin/env python3
"""
Check actual cheque numbers in the database for the unmatched transactions.
OCR may have misread the numbers.
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
    print('CHECKING ACTUAL CHEQUE NUMBERS IN DATABASE')
    print('=' * 80)
    print()

    # Check March 2012 for $150 and $100
    print('March 2012 - Looking for $150 and $100:')
    cur.execute('''
        SELECT transaction_id, transaction_date, description, debit_amount
        FROM banking_transactions
        WHERE transaction_date BETWEEN '2012-03-15' AND '2012-03-25'
        AND debit_amount BETWEEN 50 AND 200
        ORDER BY transaction_date, debit_amount
    ''')
    
    for row in cur.fetchall():
        print(f'{row[0]}: {row[1]} | ${row[3]:>8.2f} | {row[2][:70]}')
    
    print()
    print('July 2012 - Looking for $1,050:')
    cur.execute('''
        SELECT transaction_id, transaction_date, description, debit_amount
        FROM banking_transactions
        WHERE transaction_date BETWEEN '2012-07-08' AND '2012-07-15'
        AND debit_amount BETWEEN 1000 AND 1100
        ORDER BY transaction_date, debit_amount
    ''')
    
    for row in cur.fetchall():
        print(f'{row[0]}: {row[1]} | ${row[3]:>8.2f} | {row[2][:70]}')
    
    print()
    print('=' * 80)
    print('CHEQUE NUMBERS ALREADY IN REGISTER')
    print('=' * 80)
    print()
    
    cur.execute('''
        SELECT cheque_number, amount, payee
        FROM cheque_register
        WHERE cheque_number IN ('215', '216', '276')
        ORDER BY cheque_number
    ''')
    
    results = cur.fetchall()
    if results:
        print(f'Found {len(results)} existing:')
        for row in results:
            print(f'Cheque {row[0]}: ${row[1]:,.2f} | {row[2]}')
    else:
        print('None of these cheque numbers exist in register')
    
    print()
    print('=' * 80)
    print('EXTRACT CHEQUE NUMBER FROM BANKING DESCRIPTIONS')
    print('=' * 80)
    print()
    
    # Extract cheque numbers from descriptions for the target amounts
    print('Extracting cheque numbers for $150.00 around March 19:')
    cur.execute('''
        SELECT transaction_id, transaction_date, description, debit_amount
        FROM banking_transactions
        WHERE ABS(debit_amount - 150.00) < 0.01
        AND transaction_date BETWEEN '2012-03-15' AND '2012-03-25'
    ''')
    for row in cur.fetchall():
        # Try to extract cheque number from description
        desc = row[2]
        if 'Cheque' in desc or 'cheque' in desc or 'CHEQUE' in desc:
            print(f'{row[0]}: {row[1]} | ${row[3]:,.2f}')
            print(f'  Description: {desc}')
    
    print()
    print('Extracting cheque numbers for $100.00 around March 19:')
    cur.execute('''
        SELECT transaction_id, transaction_date, description, debit_amount
        FROM banking_transactions
        WHERE ABS(debit_amount - 100.00) < 0.01
        AND transaction_date BETWEEN '2012-03-15' AND '2012-03-25'
    ''')
    for row in cur.fetchall():
        desc = row[2]
        if 'Cheque' in desc or 'cheque' in desc or 'CHEQUE' in desc:
            print(f'{row[0]}: {row[1]} | ${row[3]:,.2f}')
            print(f'  Description: {desc}')
    
    print()
    print('Extracting cheque numbers for $1,050.00 around July 10:')
    cur.execute('''
        SELECT transaction_id, transaction_date, description, debit_amount
        FROM banking_transactions
        WHERE ABS(debit_amount - 1050.00) < 0.01
        AND transaction_date BETWEEN '2012-07-05' AND '2012-07-15'
    ''')
    for row in cur.fetchall():
        desc = row[2]
        if 'Cheque' in desc or 'cheque' in desc or 'CHEQUE' in desc:
            print(f'{row[0]}: {row[1]} | ${row[3]:,.2f}')
            print(f'  Description: {desc}')

    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
