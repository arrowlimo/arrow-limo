#!/usr/bin/env python3
"""
Check the actual verified banking_transactions data for July 2012.
Look for cheque 276 that was shown in the CIBC statement.
"""

import psycopg2

def main():
    conn = psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REDACTED***'
    )
    cur = conn.cursor()

    print('=' * 80)
    print('VERIFIED BANKING_TRANSACTIONS DATA - JULY 2012')
    print('Looking for Cheque 276: $1,050.00 on Jul 10, 2012')
    print('=' * 80)
    print()

    # Show all July 10 transactions
    print('All transactions on July 10, 2012:')
    cur.execute('''
        SELECT transaction_id, account_number, transaction_date, description, 
               debit_amount, credit_amount, balance
        FROM banking_transactions
        WHERE transaction_date = '2012-07-10'
        ORDER BY transaction_id
    ''')
    
    results = cur.fetchall()
    if results:
        for r in results:
            print(f'{r[0]}: Account {r[1]}')
            print(f'  Date: {r[2]}')
            print(f'  Debit: ${r[4] or 0:,.2f} | Credit: ${r[5] or 0:,.2f} | Balance: ${r[6] or 0:,.2f}')
            print(f'  Description: {r[3]}')
            print()
    else:
        print('  No transactions found on July 10, 2012')
    
    print()
    print('All transactions with $1,050 amount in July 2012:')
    cur.execute('''
        SELECT transaction_id, account_number, transaction_date, description, 
               debit_amount, credit_amount
        FROM banking_transactions
        WHERE transaction_date BETWEEN '2012-07-01' AND '2012-07-31'
        AND (ABS(debit_amount - 1050.00) < 0.01 OR ABS(credit_amount - 1050.00) < 0.01)
        ORDER BY transaction_date
    ''')
    
    results = cur.fetchall()
    if results:
        for r in results:
            amount = r[4] if r[4] else r[5]
            print(f'{r[0]}: {r[2]} | Account {r[1]} | ${amount:,.2f}')
            print(f'  {r[3]}')
            print()
    else:
        print('  No $1,050 transactions found in July 2012')
    
    print()
    print('=' * 80)
    print('CHECKING FOR CHEQUE-RELATED TRANSACTIONS IN JULY 2012')
    print('=' * 80)
    print()
    
    cur.execute('''
        SELECT transaction_id, account_number, transaction_date, description, debit_amount
        FROM banking_transactions
        WHERE transaction_date BETWEEN '2012-07-01' AND '2012-07-31'
        AND (description ILIKE '%cheque%' OR description ILIKE '%chq%' OR description ILIKE '%check%')
        ORDER BY transaction_date, debit_amount DESC
        LIMIT 20
    ''')
    
    results = cur.fetchall()
    if results:
        print(f'Found {len(results)} cheque transactions:')
        for r in results:
            print(f'{r[0]}: {r[2]} | ${r[4]:,.2f} | {r[3][:70]}')
    else:
        print('No cheque transactions found')

    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
