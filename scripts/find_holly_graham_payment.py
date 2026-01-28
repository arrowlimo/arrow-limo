#!/usr/bin/env python3
"""
Search for the Square payment for Holly Graham around May 16, 2018
Charter 015808 shows $1,417.20 balance but no linked payment
"""

import psycopg2
import os

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***')
    )

def main():
    conn = get_db_connection()
    cur = conn.cursor()

    print('=' * 80)
    print('SEARCHING FOR SQUARE PAYMENT - MAY 2018 - HOLLY GRAHAM - $1,417.20')
    print('=' * 80)

    # Search for payments in May 2018 with amount close to 1417.20
    cur.execute('''
        SELECT 
            p.payment_id,
            p.reserve_number,
            p.account_number,
            p.payment_date,
            p.amount,
            p.payment_method,
            p.square_transaction_id,
            p.square_payment_id,
            p.square_card_brand,
            p.square_last4,
            p.square_customer_name,
            p.square_gross_sales,
            p.square_net_sales,
            p.charter_id,
            cl.client_name
        FROM payments p
        LEFT JOIN clients cl ON p.client_id = cl.client_id
        WHERE p.payment_date >= '2018-05-01'::date
          AND p.payment_date <= '2018-05-31'::date
          AND (p.amount BETWEEN 1400 AND 1450
               OR p.square_gross_sales BETWEEN 1400 AND 1450)
        ORDER BY p.payment_date, p.amount DESC
    ''')

    payments = cur.fetchall()
    print(f'\nFound {len(payments)} payment(s) in May 2018 between $1,400-$1,450:')

    for pmt in payments:
        print('\n' + '=' * 80)
        print(f'Payment ID: {pmt[0]}')
        print(f'  Reserve Number: {pmt[1]}')
        print(f'  Account Number: {pmt[2]}')
        print(f'  Date: {pmt[3]}')
        print(f'  Amount: ${pmt[4]:,.2f}')
        print(f'  Method: {pmt[5]}')
        if pmt[6]:
            print(f'  Square Transaction ID: {pmt[6]}')
        if pmt[7]:
            print(f'  Square Payment ID: {pmt[7]}')
        if pmt[8]:
            print(f'  Square Card: {pmt[8]} ending {pmt[9]}')
        if pmt[10]:
            print(f'  Square Customer: {pmt[10]}')
        if pmt[11]:
            print(f'  Square Gross Sales: ${pmt[11]:,.2f}')
        if pmt[12]:
            print(f'  Square Net Sales: ${pmt[12]:,.2f}')
        charter_status = f'Linked to charter {pmt[13]}' if pmt[13] else '[FAIL] UNMATCHED'
        print(f'  Charter: {charter_status}')
        if pmt[14]:
            print(f'  Client Name: {pmt[14]}')

    # Also search by client name (Holly Graham)
    print('\n\n' + '=' * 80)
    print('SEARCHING FOR ALL HOLLY GRAHAM PAYMENTS (ANY DATE)')
    print('=' * 80)

    cur.execute('''
        SELECT 
            p.payment_id,
            p.reserve_number,
            p.payment_date,
            p.amount,
            p.payment_method,
            p.square_transaction_id,
            p.square_gross_sales,
            p.charter_id,
            cl.client_name,
            p.square_customer_name
        FROM payments p
        LEFT JOIN clients cl ON p.client_id = cl.client_id
        WHERE LOWER(cl.client_name) LIKE '%holly%'
           OR LOWER(cl.client_name) LIKE '%graham%'
           OR LOWER(p.square_customer_name) LIKE '%holly%'
           OR LOWER(p.square_customer_name) LIKE '%graham%'
        ORDER BY p.payment_date DESC
    ''')

    holly_payments = cur.fetchall()
    print(f'\nFound {len(holly_payments)} payment(s) for Holly/Graham:\n')

    for pmt in holly_payments:
        charter_status = f'Charter {pmt[7]}' if pmt[7] else '[FAIL] UNMATCHED'
        gross = f', Sq Gross ${pmt[6]:,.2f}' if pmt[6] else ''
        client = pmt[8] if pmt[8] else pmt[9]
        print(f'  ID {pmt[0]}: {pmt[2]} | ${pmt[3]:,.2f} | {pmt[4]} | {charter_status} | {client}{gross}')

    # Check if there's a client record for Holly Graham
    print('\n\n' + '=' * 80)
    print('CHECKING CLIENT RECORDS FOR HOLLY GRAHAM')
    print('=' * 80)

    cur.execute('''
        SELECT client_id, client_name, email, square_customer_id
        FROM clients
        WHERE LOWER(client_name) LIKE '%holly%'
           OR LOWER(client_name) LIKE '%graham%'
    ''')

    clients = cur.fetchall()
    if clients:
        print(f'\nFound {len(clients)} client record(s):')
        for cl in clients:
            print(f'\n  Client ID: {cl[0]}')
            print(f'    Name: {cl[1]}')
            print(f'    Email: {cl[2]}')
            print(f'    Square Customer ID: {cl[3]}')
    else:
        print('\n[FAIL] No client record found for Holly Graham')

    # Search for any payment with exact amount $1,417.20
    print('\n\n' + '=' * 80)
    print('SEARCHING FOR ANY PAYMENT OF EXACTLY $1,417.20')
    print('=' * 80)

    cur.execute('''
        SELECT 
            p.payment_id,
            p.reserve_number,
            p.payment_date,
            p.amount,
            p.payment_method,
            p.charter_id,
            cl.client_name,
            p.square_transaction_id
        FROM payments p
        LEFT JOIN clients cl ON p.client_id = cl.client_id
        WHERE p.amount = 1417.20
        ORDER BY p.payment_date DESC
        LIMIT 20
    ''')

    exact_payments = cur.fetchall()
    print(f'\nFound {len(exact_payments)} payment(s) of exactly $1,417.20:')
    
    for pmt in exact_payments:
        charter_status = f'Charter {pmt[5]}' if pmt[5] else '[FAIL] UNMATCHED'
        sq_txn = f', Sq: {pmt[7][:20]}...' if pmt[7] else ''
        client = pmt[6] if pmt[6] else 'Unknown'
        print(f'  ID {pmt[0]}: {pmt[2]} | {pmt[1]} | {pmt[4]} | {charter_status} | {client}{sq_txn}')

    cur.close()
    conn.close()

    print('\n\n' + '=' * 80)
    print('RECOMMENDATION:')
    print('=' * 80)
    print('Charter 015808 details:')
    print('  Date: 2021-06-26')
    print('  Rate: $181.00')
    print('  Balance: $1,417.20')
    print('  Status: Closed = TRUE')
    print('')
    print('This charter is marked CLOSED but has $1,417.20 balance owing.')
    print('The Square receipt you have shows $1,417.20 from May 16, 2018.')
    print('')
    print('POSSIBLE ISSUES:')
    print('  1. Payment date mismatch (May 2018 vs charter June 2021)')
    print('  2. Payment was imported but never linked to charter')
    print('  3. Charter date may be incorrect in database')
    print('  4. This could be a different transaction entirely')

if __name__ == '__main__':
    main()
