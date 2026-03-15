#!/usr/bin/env python3
"""
Add 6 new cheques to the cheque_register.
These cheques were found in the QuickBooks reconciliation PDF but not in the register.
"""

import psycopg2
from datetime import datetime

NEW_CHEQUES = [
    {'cheque_num': 215, 'date': '2012-03-19', 'payee': 'Deblown Algan', 'amount': 150.00},
    {'cheque_num': 216, 'date': '2012-03-19', 'payee': 'Sarah Odwald', 'amount': 100.00},
    {'cheque_num': 232, 'date': '2012-05-17', 'payee': 'Heffner Circle', 'amount': 1900.50},
    {'cheque_num': 233, 'date': '2012-06-20', 'payee': 'Heffner Circle Service', 'amount': 1900.50},
    {'cheque_num': 261, 'date': '2012-05-29', 'payee': 'Ike Tineo', 'amount': 2700.00},
    {'cheque_num': 276, 'date': '2012-07-10', 'payee': 'Classico', 'amount': 1050.00},
]

def find_banking_transaction(cur, cheque_date, amount):
    """Find banking transaction by date and amount (debit)."""
    # Try exact date first - any debit transaction
    cur.execute('''
        SELECT transaction_id, transaction_date, description, debit_amount
        FROM banking_transactions
        WHERE transaction_date = %s
        AND ABS(debit_amount - %s) < 0.01
        AND debit_amount > 0
        ORDER BY transaction_id
        LIMIT 1
    ''', (cheque_date, amount))
    
    result = cur.fetchone()
    if result:
        return result
    
    # Try ±1 day
    cur.execute('''
        SELECT transaction_id, transaction_date, description, debit_amount
        FROM banking_transactions
        WHERE transaction_date BETWEEN (%s::date - interval '1 day')::date AND (%s::date + interval '1 day')::date
        AND ABS(debit_amount - %s) < 0.01
        AND debit_amount > 0
        ORDER BY transaction_id
        LIMIT 1
    ''', (cheque_date, cheque_date, amount))
    
    return cur.fetchone()

def main():
    conn = psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REDACTED***'
    )
    cur = conn.cursor()

    print('=' * 80)
    print('ADDING 6 NEW CHEQUES TO REGISTER')
    print('=' * 80)
    print()

    added = 0
    skipped = 0
    
    for cheque in NEW_CHEQUES:
        cheque_date = datetime.strptime(cheque['date'], '%Y-%m-%d').date()
        
        # Find matching banking transaction
        bank_result = find_banking_transaction(cur, cheque_date, cheque['amount'])
        
        if bank_result:
            bank_id, bank_date, bank_desc, bank_amt = bank_result
            date_diff = abs((bank_date - cheque_date).days)
            
            print(f"Cheque {cheque['cheque_num']}: {cheque['date']} | ${cheque['amount']:,.2f} | {cheque['payee']}")
            print(f"  → Banking {bank_id}: {bank_date} | ${bank_amt:,.2f} | {bank_desc}")
            print(f"  Date difference: {date_diff} day(s)")
            
            # Insert into cheque_register
            cur.execute('''
                INSERT INTO cheque_register (cheque_number, banking_transaction_id, payee, amount)
                VALUES (%s, %s, %s, %s)
            ''', (str(cheque['cheque_num']), bank_id, cheque['payee'], cheque['amount']))
            
            added += 1
            print('  [OK] Added to register')
        else:
            print(f"Cheque {cheque['cheque_num']}: {cheque['date']} | ${cheque['amount']:,.2f} | {cheque['payee']}")
            print('  [FAIL] No matching banking transaction found')
            skipped += 1
        
        print()
    
    print('=' * 80)
    print('SUMMARY')
    print('=' * 80)
    print(f'Added to register: {added}')
    print(f'Skipped (no bank match): {skipped}')
    print(f'Total: {len(NEW_CHEQUES)}')
    
    # Commit changes
    conn.commit()
    print()
    print('[OK] Changes committed to database')
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
