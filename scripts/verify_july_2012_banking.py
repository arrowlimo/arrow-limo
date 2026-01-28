#!/usr/bin/env python3
"""
Verify July 2012 banking data and check for cheques 215, 216, 276.
User provided actual CIBC statement showing these cleared.
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
    print('JULY 2012 BANKING DATA VERIFICATION')
    print('=' * 80)
    print()

    # Check if we have ANY July 2012 data
    print('Checking for July 2012 banking transactions:')
    cur.execute('''
        SELECT COUNT(*), MIN(transaction_date), MAX(transaction_date)
        FROM banking_transactions
        WHERE transaction_date BETWEEN '2012-07-01' AND '2012-07-31'
    ''')
    
    count, min_date, max_date = cur.fetchone()
    print(f'  Found {count} transactions from {min_date} to {max_date}')
    print()

    # Check specifically for the balance forward from Jul 03
    print('Looking for Jul 03 Balance forward (-$620.37):')
    cur.execute('''
        SELECT transaction_id, transaction_date, description, debit_amount, credit_amount, balance
        FROM banking_transactions
        WHERE transaction_date = '2012-07-03'
        AND (description LIKE '%Balance%' OR description LIKE '%forward%')
    ''')
    
    results = cur.fetchall()
    if results:
        for r in results:
            print(f'  {r[0]}: {r[1]} | Debit: ${r[3] or 0:.2f} | Credit: ${r[4] or 0:.2f} | Balance: ${r[5] or 0:.2f}')
            print(f'  Description: {r[2]}')
    else:
        print('  Not found - July 2012 statement data may not be imported')
    
    print()
    
    # Check for March 2012 transactions around cheques 215/216
    print('=' * 80)
    print('MARCH 2012 DATA - CHEQUES 215 & 216')
    print('=' * 80)
    print()
    
    print('Looking for $150.00 and $100.00 transactions in March 2012:')
    cur.execute('''
        SELECT transaction_id, transaction_date, description, debit_amount
        FROM banking_transactions
        WHERE transaction_date BETWEEN '2012-03-01' AND '2012-03-31'
        AND (debit_amount BETWEEN 99 AND 101 OR debit_amount BETWEEN 149 AND 151)
        ORDER BY transaction_date, debit_amount
    ''')
    
    results = cur.fetchall()
    if results:
        print(f'  Found {len(results)} potential matches:')
        for r in results:
            print(f'  {r[0]}: {r[1]} | ${r[3]:,.2f} | {r[2][:70]}')
    else:
        print('  No $150 or $100 transactions found in March 2012')
    
    print()
    
    # Check what months DO have data
    print('=' * 80)
    print('AVAILABLE 2012 BANKING DATA BY MONTH')
    print('=' * 80)
    print()
    
    cur.execute('''
        SELECT 
            TO_CHAR(transaction_date, 'YYYY-MM') as month,
            COUNT(*) as transactions,
            MIN(transaction_date) as first_date,
            MAX(transaction_date) as last_date
        FROM banking_transactions
        WHERE EXTRACT(YEAR FROM transaction_date) = 2012
        GROUP BY TO_CHAR(transaction_date, 'YYYY-MM')
        ORDER BY month
    ''')
    
    for row in cur.fetchall():
        print(f'{row[0]}: {row[1]:>4} transactions ({row[2]} to {row[3]})')

    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
