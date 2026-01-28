#!/usr/bin/env python3
"""
Search for Holly Graham charter around June 25, 2021
Email subject: "L23 holly Graham" from info@arrowlimo.ca
Sent: 25/06/2021 12:17:46
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
    print('SEARCHING FOR HOLLY GRAHAM CHARTER - JUNE 2021 - L23')
    print('Email: 25/06/2021 12:17:46 - Subject: "L23 holly Graham"')
    print('=' * 80)

    # Search for Holly Graham charters in late June 2021
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
            c.vehicle,
            c.driver,
            c.pickup_address,
            c.dropoff_address,
            c.notes,
            cl.client_name,
            cl.email,
            cl.client_id
        FROM charters c
        LEFT JOIN clients cl ON c.client_id = cl.client_id
        WHERE c.charter_date BETWEEN '2021-06-20' AND '2021-06-30'
          AND (LOWER(cl.client_name) LIKE '%holly%' 
               OR LOWER(cl.client_name) LIKE '%graham%')
        ORDER BY c.charter_date
    """)

    charters = cur.fetchall()
    print(f'\nFound {len(charters)} charter(s) for Holly Graham in late June 2021:\n')
    
    for ch in charters:
        print('=' * 80)
        print(f'Charter ID: {ch[0]}')
        print(f'  Reserve Number: {ch[1]}')
        print(f'  Date: {ch[2]} at {ch[3]}')
        print(f'  Client: {ch[16]} (ID: {ch[18]})')
        if ch[17]:
            print(f'  Email: {ch[17]}')
        print(f'  Rate: ${ch[4]:,.2f}' if ch[4] else '  Rate: NULL')
        print(f'  Balance: ${ch[5]:,.2f}' if ch[5] else '  Balance: NULL')
        print(f'  Deposit: ${ch[6]:,.2f}' if ch[6] else '  Deposit: NULL')
        print(f'  Paid Amount: ${ch[7]:,.2f}' if ch[7] else '  Paid Amount: NULL')
        print(f'  Total Due: ${ch[8]:,.2f}' if ch[8] else '  Total Due: NULL')
        print(f'  Status: {ch[9]}')
        print(f'  Closed: {ch[10]}')
        print(f'  Vehicle: {ch[11]}' if ch[11] else '  Vehicle: Not assigned')
        print(f'  Driver: {ch[12]}' if ch[12] else '  Driver: Not assigned')
        print(f'  Pickup: {ch[13]}' if ch[13] else '  Pickup: Not specified')
        print(f'  Dropoff: {ch[14]}' if ch[14] else '  Dropoff: Not specified')
        if ch[15]:
            notes = ch[15][:300] + '...' if len(ch[15]) > 300 else ch[15]
            print(f'  Notes: {notes}')
        print()
        
        charter_id = ch[0]
        
        # Get payments for this charter
        cur.execute("""
            SELECT 
                p.payment_id,
                p.payment_date,
                p.amount,
                p.payment_method,
                p.payment_key,
                p.square_transaction_id,
                p.square_gross_sales,
                p.notes
            FROM payments p
            WHERE p.charter_id = %s
            ORDER BY p.payment_date
        """, (charter_id,))
        
        payments = cur.fetchall()
        if payments:
            print(f'  PAYMENTS ({len(payments)} total):')
            for pmt in payments:
                print(f'    - Payment ID {pmt[0]}: ${pmt[2]:,.2f} on {pmt[1]} ({pmt[3]})')
                if pmt[4]:
                    print(f'      Key: {pmt[4]}')
                if pmt[5]:
                    print(f'      Square Txn: {pmt[5]}')
                if pmt[6]:
                    print(f'      Square Gross: ${pmt[6]:,.2f}')
        else:
            print('  [FAIL] NO PAYMENTS LINKED TO THIS CHARTER!')

    # Check if vehicle L23 exists
    print('\n' + '=' * 80)
    print('CHECKING FOR VEHICLE "L23"')
    print('=' * 80)
    
    cur.execute("""
        SELECT vehicle_id, unit_number, vehicle_type, make, model, year, license_plate
        FROM vehicles
        WHERE LOWER(unit_number) LIKE '%l23%'
           OR LOWER(license_plate) LIKE '%l23%'
           OR LOWER(vehicle_type) LIKE '%l23%'
    """)
    
    vehicles = cur.fetchall()
    if vehicles:
        print(f'\nFound {len(vehicles)} vehicle(s) matching "L23":')
        for v in vehicles:
            print(f'\n  Vehicle ID: {v[0]}')
            print(f'    Unit: {v[1]}')
            print(f'    Type: {v[2]}')
            print(f'    Make/Model: {v[3]} {v[4]} {v[5]}')
            print(f'    License: {v[6]}')
    else:
        print('\nNo vehicle found with "L23" identifier.')
        print('L23 is likely a booking reference or vehicle assignment code.')

    cur.close()
    conn.close()

    print('\n' + '=' * 80)
    print('ANALYSIS:')
    print('=' * 80)
    print('Email sent: June 25, 2021 at 12:17 PM')
    print('Subject: "L23 holly Graham"')
    print('')
    print('This email was likely sent as a booking confirmation or assignment.')
    print('L23 could be:')
    print('  - Vehicle assignment code')
    print('  - Booking reference')
    print('  - Limousine unit number')
    print('')
    print('Charter 015808 shows:')
    print('  - Date: June 26, 2021 (day AFTER email)')
    print('  - Rate: $181.00')
    print('  - Balance: $1,417.20 (UNPAID!)')
    print('  - Status: Closed = TRUE')
    print('')
    print('The email on June 25 was likely sent when booking was made.')
    print('The charter ran on June 26.')
    print('But the payment of $1,417.20 was never linked to this charter!')

if __name__ == '__main__':
    main()
