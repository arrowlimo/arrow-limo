#!/usr/bin/env python3
"""
Verify Square payment for reservation 015808 (Holly Graham)
Square receipt shows $1,417.20 but user states $1,470.20
"""

import psycopg2
import os
from datetime import datetime

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REDACTED***')
    )

def main():
    conn = get_db_connection()
    cur = conn.cursor()

    print('=' * 80)
    print('RESERVATION 015808 - HOLLY GRAHAM VERIFICATION')
    print('=' * 80)

    # Get charter details
    cur.execute('''
        SELECT 
            c.charter_id,
            c.reserve_number,
            c.charter_date,
            c.pickup_time,
            c.client_id,
            cl.client_name,
            c.rate,
            c.balance,
            c.deposit,
            c.paid_amount,
            c.total_amount_due,
            c.status,
            c.closed,
            c.notes
        FROM charters c
        LEFT JOIN clients cl ON c.client_id = cl.client_id
        WHERE c.reserve_number = '015808'
    ''')

    charter = cur.fetchone()
    if charter:
        print(f'\nCHARTER DETAILS:')
        print(f'  Charter ID: {charter[0]}')
        print(f'  Reserve Number: {charter[1]}')
        print(f'  Charter Date: {charter[2]}')
        print(f'  Pickup Time: {charter[3]}')
        print(f'  Client ID: {charter[4]}')
        print(f'  Client Name: {charter[5]}')
        print(f'  Rate: ${charter[6]:,.2f}' if charter[6] else '  Rate: NULL')
        print(f'  Balance: ${charter[7]:,.2f}' if charter[7] else '  Balance: NULL')
        print(f'  Deposit: ${charter[8]:,.2f}' if charter[8] else '  Deposit: NULL')
        print(f'  Paid Amount: ${charter[9]:,.2f}' if charter[9] else '  Paid Amount: NULL')
        print(f'  Total Due: ${charter[10]:,.2f}' if charter[10] else '  Total Due: NULL')
        print(f'  Status: {charter[11]}')
        print(f'  Closed: {charter[12]}')
        if charter[13]:
            notes = charter[13][:200] + '...' if len(charter[13]) > 200 else charter[13]
            print(f'  Notes: {notes}')
        
        charter_id = charter[0]
    else:
        print('\n[FAIL] Charter 015808 not found!')
        cur.close()
        conn.close()
        return

    # Get all payments for this charter
    cur.execute('''
        SELECT 
            p.payment_id,
            p.payment_date,
            p.amount,
            p.payment_method,
            p.payment_key,
            p.square_transaction_id,
            p.square_payment_id,
            p.square_card_brand,
            p.square_last4,
            p.square_customer_name,
            p.square_gross_sales,
            p.square_net_sales,
            p.square_tip,
            p.square_status,
            p.square_notes,
            p.notes,
            p.status
        FROM payments p
        WHERE p.charter_id = %s
        ORDER BY p.payment_date, p.payment_id
    ''', (charter_id,))

    payments = cur.fetchall()
    if payments:
        print(f'\n\nPAYMENTS LINKED TO CHARTER ({len(payments)} total):')
        print('-' * 80)
        total = 0
        for i, pmt in enumerate(payments, 1):
            print(f'\nPayment #{i}:')
            print(f'  Payment ID: {pmt[0]}')
            print(f'  Date: {pmt[1]}')
            print(f'  Amount: ${pmt[2]:,.2f}')
            print(f'  Method: {pmt[3]}')
            print(f'  Payment Key: {pmt[4]}')
            if pmt[5]:
                print(f'  Square Transaction ID: {pmt[5]}')
            if pmt[6]:
                print(f'  Square Payment ID: {pmt[6]}')
            if pmt[7]:
                print(f'  Square Card: {pmt[7]} ending {pmt[8]}')
            if pmt[9]:
                print(f'  Square Customer: {pmt[9]}')
            if pmt[10]:
                print(f'  Square Gross Sales: ${pmt[10]:,.2f}')
            if pmt[11]:
                print(f'  Square Net Sales: ${pmt[11]:,.2f}')
            if pmt[12]:
                print(f'  Square Tip: ${pmt[12]:,.2f}')
            if pmt[13]:
                print(f'  Square Status: {pmt[13]}')
            if pmt[14]:
                notes = pmt[14][:100] + '...' if len(pmt[14]) > 100 else pmt[14]
                print(f'  Square Notes: {notes}')
            if pmt[15]:
                notes = pmt[15][:100] + '...' if len(pmt[15]) > 100 else pmt[15]
                print(f'  Notes: {notes}')
            print(f'  Status: {pmt[16]}')
            total += float(pmt[2]) if pmt[2] else 0
        
        print(f'\n  TOTAL PAYMENTS: ${total:,.2f}')
    else:
        print('\n\n[FAIL] No payments linked to this charter!')

    # Search for unmatched payment of 1470.20
    print('\n\n' + '=' * 80)
    print('SEARCHING FOR PAYMENT OF $1,470.20 (User-stated amount)')
    print('=' * 80)

    cur.execute('''
        SELECT 
            p.payment_id,
            p.reserve_number,
            p.account_number,
            p.payment_date,
            p.amount,
            p.payment_method,
            p.payment_key,
            p.square_transaction_id,
            p.square_gross_sales,
            p.square_net_sales,
            p.square_customer_name,
            p.charter_id,
            cl.client_name
        FROM payments p
        LEFT JOIN clients cl ON p.client_id = cl.client_id
        WHERE p.amount BETWEEN 1470.00 AND 1470.50
        ORDER BY p.payment_date DESC
    ''')

    matches = cur.fetchall()
    if matches:
        print(f'\nFound {len(matches)} payment(s) matching $1,470.20:')
        print('-' * 80)
        for pmt in matches:
            print(f'\nPayment ID: {pmt[0]}')
            print(f'  Reserve Number: {pmt[1]}')
            print(f'  Account Number: {pmt[2]}')
            print(f'  Date: {pmt[3]}')
            print(f'  Amount: ${pmt[4]:,.2f}')
            print(f'  Method: {pmt[5]}')
            print(f'  Payment Key: {pmt[6]}')
            if pmt[7]:
                print(f'  Square Transaction ID: {pmt[7]}')
            if pmt[8]:
                print(f'  Square Gross Sales: ${pmt[8]:,.2f}')
            if pmt[9]:
                print(f'  Square Net Sales: ${pmt[9]:,.2f}')
            if pmt[10]:
                print(f'  Square Customer: {pmt[10]}')
            charter_status = f"Linked to charter {pmt[11]}" if pmt[11] else "[FAIL] UNMATCHED"
            print(f'  Charter: {charter_status}')
            if pmt[12]:
                print(f'  Client Name: {pmt[12]}')
    else:
        print('\n[FAIL] No payment of $1,470.20 found!')

    # Search for 1417.20 (net sales from Square receipt)
    print('\n\n' + '=' * 80)
    print('SEARCHING FOR PAYMENT OF $1,417.20 (Square Receipt Amount)')
    print('=' * 80)

    cur.execute('''
        SELECT 
            p.payment_id,
            p.reserve_number,
            p.account_number,
            p.payment_date,
            p.amount,
            p.payment_method,
            p.payment_key,
            p.square_transaction_id,
            p.square_gross_sales,
            p.square_net_sales,
            p.square_customer_name,
            p.charter_id,
            cl.client_name
        FROM payments p
        LEFT JOIN clients cl ON p.client_id = cl.client_id
        WHERE p.amount BETWEEN 1417.00 AND 1417.50
           OR p.square_gross_sales BETWEEN 1417.00 AND 1417.50
           OR p.square_net_sales BETWEEN 1417.00 AND 1417.50
        ORDER BY p.payment_date DESC
        LIMIT 20
    ''')

    matches = cur.fetchall()
    if matches:
        print(f'\nFound {len(matches)} payment(s) matching $1,417.20:')
        print('-' * 80)
        for pmt in matches:
            print(f'\nPayment ID: {pmt[0]}')
            print(f'  Reserve Number: {pmt[1]}')
            print(f'  Account Number: {pmt[2]}')
            print(f'  Date: {pmt[3]}')
            print(f'  Amount: ${pmt[4]:,.2f}')
            print(f'  Method: {pmt[5]}')
            print(f'  Payment Key: {pmt[6]}')
            if pmt[7]:
                print(f'  Square Transaction ID: {pmt[7]}')
            if pmt[8]:
                print(f'  Square Gross Sales: ${pmt[8]:,.2f}')
            if pmt[9]:
                print(f'  Square Net Sales: ${pmt[9]:,.2f}')
            if pmt[10]:
                print(f'  Square Customer: {pmt[10]}')
            charter_status = f"Linked to charter {pmt[11]}" if pmt[11] else "[FAIL] UNMATCHED"
            print(f'  Charter: {charter_status}')
            if pmt[12]:
                print(f'  Client Name: {pmt[12]}')
    else:
        print('\n[FAIL] No payment of $1,417.20 found!')

    # Search for Holly Graham payments
    print('\n\n' + '=' * 80)
    print('SEARCHING FOR ALL HOLLY GRAHAM PAYMENTS')
    print('=' * 80)

    cur.execute('''
        SELECT 
            p.payment_id,
            p.reserve_number,
            p.payment_date,
            p.amount,
            p.payment_method,
            p.square_gross_sales,
            p.square_net_sales,
            p.charter_id,
            cl.client_name
        FROM payments p
        LEFT JOIN clients cl ON p.client_id = cl.client_id
        WHERE LOWER(cl.client_name) LIKE '%holly%graham%'
           OR LOWER(p.square_customer_name) LIKE '%holly%graham%'
        ORDER BY p.payment_date DESC
    ''')

    matches = cur.fetchall()
    if matches:
        print(f'\nFound {len(matches)} payment(s) for Holly Graham:')
        print('-' * 80)
        for pmt in matches:
            print(f'\nPayment ID: {pmt[0]}')
            print(f'  Reserve Number: {pmt[1]}')
            print(f'  Date: {pmt[2]}')
            print(f'  Amount: ${pmt[3]:,.2f}')
            print(f'  Method: {pmt[4]}')
            if pmt[5]:
                print(f'  Square Gross: ${pmt[5]:,.2f}')
            if pmt[6]:
                print(f'  Square Net: ${pmt[6]:,.2f}')
            charter_status = f"Charter {pmt[7]}" if pmt[7] else "[FAIL] UNMATCHED"
            print(f'  Charter: {charter_status}')
            if pmt[8]:
                print(f'  Client: {pmt[8]}')

    cur.close()
    conn.close()

    print('\n' + '=' * 80)
    print('SQUARE RECEIPT ANALYSIS:')
    print('=' * 80)
    print('Square Receipt (May 16, 2018) shows:')
    print('  Gross Sales:     $1,417.20')
    print('  Refunds:         $0.00')
    print('  Discounts/Comps: $0.00')
    print('  Net Sales:       $1,417.20')
    print('  Tips:            $0.00')
    print('  Tax:             $0.00')
    print('  Total Collected: $1,417.20')
    print('')
    print('User stated amount: $1,470.20')
    print('Difference: $53.00 ($1,470.20 - $1,417.20)')
    print('')
    print('Possible explanations:')
    print('  1. Processing fee: Square charges 2.65% + $0.15 per transaction')
    print('     $1,417.20 × 2.65% + $0.15 = $37.71 (not matching)')
    print('  2. Two separate payments: $1,417.20 + $53.00 = $1,470.20')
    print('  3. Typo in stated amount')
    print('  4. Different transaction altogether')

if __name__ == '__main__':
    main()
