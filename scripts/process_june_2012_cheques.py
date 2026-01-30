#!/usr/bin/env python3
"""
Process June 2012 cheques from QuickBooks PDF and check for duplicates.
Compares against existing cheque_register entries by cheque number and date.
"""

import psycopg2
from datetime import datetime

# Cheques extracted from PDF images
JUNE_2012_CHEQUES = [
    # From first batch images
    {'cheque_num': 220, 'date': '2012-06-20', 'payee': 'Heffner Lexus Toyota', 'amount': 1475.25},
    {'cheque_num': 226, 'date': '2012-06-19', 'payee': 'Heffner Lexus Toyota', 'amount': 2525.25},
    {'cheque_num': 233, 'date': '2012-06-20', 'payee': 'Heffner Circle Service', 'amount': 1900.50},
    {'cheque_num': 262, 'date': '2012-06-11', 'payee': 'CFIB', 'amount': 460.00},
    {'cheque_num': 234, 'date': '2012-07-19', 'payee': 'Heffner Lexus Toyota', 'amount': 1900.50},
    {'cheque_num': 276, 'date': '2012-07-10', 'payee': 'Classico', 'amount': 1050.00},
    {'cheque_num': 277, 'date': '2012-07-16', 'payee': 'Arrow Limousine', 'amount': 400.00},
    
    {'cheque_num': 264, 'date': '2012-06-08', 'payee': 'Jesse Gordon', 'amount': 198.79},
    {'cheque_num': 265, 'date': '2012-06-18', 'payee': 'Jesse Gordon', 'amount': 377.99},
    {'cheque_num': 266, 'date': '2012-06-12', 'payee': 'Doug Redmond', 'amount': 921.46},
    {'cheque_num': 267, 'date': '2012-06-06', 'payee': 'Angel Escalo', 'amount': 2247.45},
    {'cheque_num': 268, 'date': '2012-06-08', 'payee': 'Barry Forsberg', 'amount': 123.94},
    {'cheque_num': 269, 'date': '2012-06-06', 'payee': 'Paul Mansell', 'amount': 3244.25},
    {'cheque_num': 270, 'date': '2012-06-08', 'payee': 'Mark Linton', 'amount': 176.71},
    {'cheque_num': 271, 'date': '2012-06-08', 'payee': 'Jeannie Shillington', 'amount': 3483.79},
    {'cheque_num': 272, 'date': '2012-06-06', 'payee': 'Michael Richard', 'amount': 1701.33},
    {'cheque_num': 273, 'date': '2012-06-12', 'payee': 'Barry Forsberg', 'amount': 140.00},
    {'cheque_num': 274, 'date': '2012-06-13', 'payee': 'Fibrenew', 'amount': 1050.00},
    {'cheque_num': 275, 'date': '2012-06-15', 'payee': 'Todd Happlins', 'amount': 748.00},
    
    # From new batch images
    {'cheque_num': 217, 'date': '2012-05-09', 'payee': 'Heffner Lexus Toyota', 'amount': 1475.25},
    {'cheque_num': 219, 'date': '2012-05-17', 'payee': 'Heffner Lexus Toyota', 'amount': 1475.25},
    {'cheque_num': 225, 'date': '2012-05-16', 'payee': 'Heffner Lexus Toyota', 'amount': 2525.25},
    {'cheque_num': 231, 'date': '2012-05-09', 'payee': 'Heffner Circle', 'amount': 1900.50},
    
    {'cheque_num': 232, 'date': '2012-05-17', 'payee': 'Heffner Circle', 'amount': 1900.50},
    {'cheque_num': 249, 'date': '2012-05-08', 'payee': 'Mark Linton', 'amount': 3000.00},
    {'cheque_num': 254, 'date': '2012-05-01', 'payee': 'Theresa Crosby Beyer Lawyer', 'amount': 701.86},
    {'cheque_num': 255, 'date': '2012-05-04', 'payee': 'Angel Escalo', 'amount': 1756.20},
    
    {'cheque_num': 256, 'date': '2012-05-09', 'payee': 'Theresa Kellenberger', 'amount': 1500.54},
    {'cheque_num': 257, 'date': '2012-05-07', 'payee': 'Paul Mansell', 'amount': 996.46},
    {'cheque_num': 258, 'date': '2012-05-16', 'payee': 'Jeannie Shillington', 'amount': 1588.86},
    {'cheque_num': 259, 'date': '2012-05-18', 'payee': 'Monika La Fleche', 'amount': 50.00},
    
    {'cheque_num': 260, 'date': '2012-05-16', 'payee': 'Louise Breland', 'amount': 6000.00},
    {'cheque_num': 261, 'date': '2012-05-29', 'payee': 'Ike Tineo', 'amount': 2700.00},
    {'cheque_num': 263, 'date': '2012-05-25', 'payee': 'Paul Richard', 'amount': 1000.00},
    
    # From bottom images
    {'cheque_num': 210, 'date': '2012-03-08', 'payee': 'Theresa Skillenberger', 'amount': 500.00},
    {'cheque_num': 213, 'date': '2012-03-13', 'payee': 'April Harley', 'amount': 1050.00},
    {'cheque_num': 214, 'date': '2012-03-12', 'payee': 'Heather Gullion', 'amount': 214.56},
    {'cheque_num': 215, 'date': '2012-03-19', 'payee': 'Deblown Algan', 'amount': 150.00},
    {'cheque_num': 216, 'date': '2012-03-19', 'payee': 'Sarah Odwald', 'amount': 100.00},
]

def main():
    conn = psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REDACTED***'
    )
    cur = conn.cursor()

    print('=' * 80)
    print('JUNE 2012 CHEQUES - DUPLICATE CHECK')
    print('=' * 80)
    print()

    # Check each cheque against existing register
    new_cheques = []
    duplicates = []
    
    for cheque in JUNE_2012_CHEQUES:
        cur.execute('''
            SELECT cr.cheque_number, cr.banking_transaction_id, bt.transaction_date, bt.debit_amount, cr.payee
            FROM cheque_register cr
            LEFT JOIN banking_transactions bt ON cr.banking_transaction_id = bt.transaction_id
            WHERE cr.cheque_number = %s
        ''', (str(cheque['cheque_num']),))
        
        existing = cur.fetchone()
        
        if existing:
            duplicates.append({
                'cheque': cheque,
                'existing': {
                    'cheque_num': existing[0],
                    'bank_id': existing[1],
                    'date': existing[2],
                    'amount': existing[3],
                    'payee': existing[4]
                }
            })
        else:
            new_cheques.append(cheque)
    
    # Display results
    print(f'Total cheques from PDF: {len(JUNE_2012_CHEQUES)}')
    print(f'New cheques (not in register): {len(new_cheques)}')
    print(f'Duplicates (already in register): {len(duplicates)}')
    print()
    
    if duplicates:
        print('=' * 80)
        print('DUPLICATE CHEQUES (Already in register)')
        print('=' * 80)
        for dup in duplicates:
            pdf_date = datetime.strptime(dup['cheque']['date'], '%Y-%m-%d').date()
            db_date = dup['existing']['date']
            date_match = '[OK]' if pdf_date == db_date else f'[FAIL] DB has {db_date}'
            
            pdf_amt = float(dup['cheque']['amount'])
            db_amt = float(dup['existing']['amount'])
            amt_match = '[OK]' if abs(pdf_amt - db_amt) < 0.01 else f'[FAIL] DB has ${db_amt:,.2f}'
            
            print(f"\nCheque {dup['cheque']['cheque_num']}:")
            print(f"  PDF:  {dup['cheque']['date']} | ${pdf_amt:>10,.2f} | {dup['cheque']['payee']}")
            print(f"  DB:   {db_date} | ${db_amt:>10,.2f} | {dup['existing']['payee'] or 'UNKNOWN'}")
            print(f"  Date: {date_match}  Amount: {amt_match}")
            if dup['existing']['bank_id']:
                print(f"  Linked to banking transaction: {dup['existing']['bank_id']}")
    
    if new_cheques:
        print()
        print('=' * 80)
        print('NEW CHEQUES (Not in register)')
        print('=' * 80)
        for cheque in new_cheques:
            print(f"Cheque {cheque['cheque_num']: >3}: {cheque['date']} | ${cheque['amount']:>10,.2f} | {cheque['payee']}")
    
    # Summary by date
    print()
    print('=' * 80)
    print('CHEQUES BY DATE (from PDF)')
    print('=' * 80)
    
    from collections import defaultdict
    by_date = defaultdict(list)
    for cheque in JUNE_2012_CHEQUES:
        by_date[cheque['date']].append(cheque)
    
    for date in sorted(by_date.keys()):
        cheques = by_date[date]
        total = sum(c['amount'] for c in cheques)
        print(f"\n{date}: {len(cheques)} cheques, ${total:,.2f}")
        for c in cheques:
            status = '(duplicate)' if any(d['cheque']['cheque_num'] == c['cheque_num'] for d in duplicates) else '(NEW)'
            print(f"  {c['cheque_num']: >3}: ${c['amount']:>10,.2f} | {c['payee']} {status}")

    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
