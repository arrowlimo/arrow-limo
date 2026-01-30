#!/usr/bin/env python3
"""
Add the 3 remaining cheques to register as uncleared (no banking link).
These cheques appear in the QB reconciliation but have no matching banking transaction.
"""

import psycopg2

UNCLEARED_CHEQUES = [
    {'cheque_num': 215, 'date': '2012-03-19', 'payee': 'Deblown Algan', 'amount': 150.00},
    {'cheque_num': 216, 'date': '2012-03-19', 'payee': 'Sarah Odwald', 'amount': 100.00},
    {'cheque_num': 276, 'date': '2012-07-10', 'payee': 'Classico', 'amount': 1050.00},
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
    print('ADDING UNCLEARED CHEQUES TO REGISTER')
    print('=' * 80)
    print()
    print('These cheques appear in QuickBooks but have no matching banking transaction.')
    print('They will be added to the register without a banking_transaction_id link.')
    print()

    for cheque in UNCLEARED_CHEQUES:
        print(f"Cheque {cheque['cheque_num']}: {cheque['date']} | ${cheque['amount']:,.2f} | {cheque['payee']}")
        
        # Insert into cheque_register without banking_transaction_id
        cur.execute('''
            INSERT INTO cheque_register (cheque_number, payee, amount)
            VALUES (%s, %s, %s)
        ''', (str(cheque['cheque_num']), cheque['payee'], cheque['amount']))
        
        print('  [OK] Added to register (uncleared)')
        print()
    
    print('=' * 80)
    print('SUMMARY')
    print('=' * 80)
    print(f'Added {len(UNCLEARED_CHEQUES)} uncleared cheques to register')
    print()
    print('Note: These cheques may have been:')
    print('  - Voided and never cashed')
    print('  - Outstanding (not yet cleared the bank)')
    print('  - From a different bank account not in our records')
    
    # Commit changes
    conn.commit()
    print()
    print('[OK] Changes committed to database')
    
    # Show final register status
    print()
    print('=' * 80)
    print('FINAL CHEQUE REGISTER STATUS')
    print('=' * 80)
    
    cur.execute('SELECT COUNT(*) FROM cheque_register')
    total = cur.fetchone()[0]
    
    cur.execute('SELECT COUNT(*) FROM cheque_register WHERE banking_transaction_id IS NOT NULL')
    linked = cur.fetchone()[0]
    
    cur.execute('SELECT COUNT(*) FROM cheque_register WHERE payee IS NOT NULL AND payee != \'UNKNOWN\'')
    with_payee = cur.fetchone()[0]
    
    print(f'Total cheques in register: {total}')
    print(f'Linked to banking: {linked} ({100*linked/total:.1f}%)')
    print(f'With payee names: {with_payee} ({100*with_payee/total:.1f}%)')
    print(f'Uncleared/unlinked: {total - linked} ({100*(total-linked)/total:.1f}%)')

    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
