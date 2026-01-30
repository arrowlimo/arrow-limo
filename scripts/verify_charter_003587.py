#!/usr/bin/env python3
"""
Verify charter 003587 (King Kent) from LMS screenshot
Date: 08/13/2012
Payment: $231.00 Visa, RECEIVED, Balance $0.00
"""

import psycopg2
import os

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
    print('CHARTER 003587 - KING KENT - AUGUST 13, 2012')
    print('=' * 80)

    # Get charter details
    cur.execute("""
        SELECT 
            c.charter_id,
            c.reserve_number,
            c.charter_date,
            c.pickup_time,
            c.rate,
            c.balance,
            c.deposit,
            c.paid_amount,
            c.total_amount_due,
            c.status,
            c.closed,
            c.cancelled,
            cl.client_name,
            cl.email,
            c.vehicle,
            c.driver,
            c.notes
        FROM charters c
        LEFT JOIN clients cl ON c.client_id = cl.client_id
        WHERE c.reserve_number = '003587'
    """)

    charter = cur.fetchone()
    if charter:
        print(f'\nCHARTER DETAILS:')
        print(f'  Charter ID: {charter[0]}')
        print(f'  Reserve Number: {charter[1]}')
        print(f'  Date: {charter[2]} at {charter[3]}')
        print(f'  Rate: ${charter[4]:,.2f}' if charter[4] else '  Rate: $0.00 or NULL')
        print(f'  Balance: ${charter[5]:,.2f}' if charter[5] else '  Balance: $0.00 or NULL')
        print(f'  Deposit: ${charter[6]:,.2f}' if charter[6] else '  Deposit: $0.00 or NULL')
        print(f'  Paid Amount: ${charter[7]:,.2f}' if charter[7] else '  Paid Amount: $0.00 or NULL')
        print(f'  Total Due: ${charter[8]:,.2f}' if charter[8] else '  Total Due: $0.00 or NULL')
        print(f'  Status: {charter[9]}')
        print(f'  Closed: {charter[10]}')
        print(f'  Cancelled: {charter[11]}')
        print(f'  Client: {charter[12]}')
        print(f'  Email: {charter[13]}')
        print(f'  Vehicle: {charter[14]}')
        print(f'  Driver: {charter[15]}')
        if charter[16]:
            print(f'  Notes: {charter[16][:200]}...' if len(charter[16]) > 200 else f'  Notes: {charter[16]}')
        
        charter_id = charter[0]
        
        # Get payments
        cur.execute("""
            SELECT 
                p.payment_id,
                p.payment_date,
                p.amount,
                p.payment_method,
                p.payment_key,
                p.notes,
                p.status
            FROM payments p
            WHERE p.charter_id = %s
            ORDER BY p.payment_date
        """, (charter_id,))
        
        payments = cur.fetchall()
        if payments:
            print(f'\n\nPAYMENTS ({len(payments)} total):')
            print('-' * 80)
            total = 0
            for pmt in payments:
                print(f'\n  Payment ID: {pmt[0]}')
                print(f'    Date: {pmt[1]}')
                print(f'    Amount: ${pmt[2]:,.2f}')
                print(f'    Method: {pmt[3]}')
                print(f'    Key: {pmt[4]}')
                if pmt[5]:
                    print(f'    Notes: {pmt[5][:100]}...' if len(pmt[5]) > 100 else f'    Notes: {pmt[5]}')
                print(f'    Status: {pmt[6]}')
                total += float(pmt[2]) if pmt[2] else 0
            
            print(f'\n  TOTAL PAYMENTS: ${total:,.2f}')
        else:
            print('\n\n[FAIL] NO PAYMENTS LINKED TO THIS CHARTER!')
    else:
        print('\n[FAIL] Charter 003587 not found in database!')

    cur.close()
    conn.close()

    print('\n\n' + '=' * 80)
    print('LMS SCREENSHOT DATA:')
    print('=' * 80)
    print('Reserve: 003587')
    print('Bill To: 01305 - King Kent')
    print('Date: 08/13/2012 (MMW)')
    print('Pickup: 13:30')
    print('Drop: 17:30')
    print('Hours: 4:00')
    print('Rate: 0.00')
    print('')
    print('Payment (08/13/2012):')
    print('  Type: Visa')
    print('  Description: RECEIVED')
    print('  Amount: $231.00')
    print('')
    print('Charges: $231.00')
    print('Deposits: -$231.00')
    print('Received: 0.00')
    print('')
    print('Total Charges: $231.00')
    print('Payments: $231.00')
    print('Balance: $0.00')
    print('')
    print('[OK] This charter is PAID IN FULL in LMS')

if __name__ == '__main__':
    main()
