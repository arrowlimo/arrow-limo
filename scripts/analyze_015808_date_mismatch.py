#!/usr/bin/env python3
"""
Deep analysis of charter 015808 - checking for date typo
Square receipt shows May 16, 2018 but charter shows June 26, 2021
Check times, mileage, driver hours for clues
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
    print('CHARTER 015808 - DETAILED ANALYSIS')
    print('Square Receipt: May 16, 2018 (Wednesday) 7:00 AM - 7:30 PM MDT')
    print('Charter Database: June 26, 2021')
    print('=' * 80)

    # Get full charter details including driver hours, mileage
    cur.execute("""
        SELECT 
            c.charter_id,
            c.reserve_number,
            c.charter_date,
            c.pickup_time,
            c.reservation_time,
            c.actual_start_time,
            c.actual_end_time,
            c.calculated_hours,
            c.driver_hours_1,
            c.driver_hours_2,
            c.driver_hours_worked,
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
            c.odometer_start,
            c.odometer_end,
            c.total_kms,
            c.notes,
            cl.client_name,
            cl.email
        FROM charters c
        LEFT JOIN clients cl ON c.client_id = cl.client_id
        WHERE c.reserve_number = '015808'
    """)

    charter = cur.fetchone()
    if charter:
        print(f'\nCHARTER 015808 - FULL DETAILS:')
        print('=' * 80)
        print(f'Charter ID: {charter[0]}')
        print(f'Reserve Number: {charter[1]}')
        print(f'Charter Date: {charter[2]}')
        print(f'Pickup Time: {charter[3]}')
        print(f'Reservation Time: {charter[4]}')
        print(f'Actual Start: {charter[5]}')
        print(f'Actual End: {charter[6]}')
        print(f'Calculated Hours: {charter[7]}')
        print(f'Driver Hours 1: {charter[8]}')
        print(f'Driver Hours 2: {charter[9]}')
        print(f'Driver Hours Worked: {charter[10]}')
        print(f'\nFINANCIALS:')
        print(f'Rate: ${charter[11]:,.2f}' if charter[11] else 'Rate: NULL')
        print(f'Balance: ${charter[12]:,.2f}' if charter[12] else 'Balance: NULL')
        print(f'Deposit: ${charter[13]:,.2f}' if charter[13] else 'Deposit: NULL')
        print(f'Paid Amount: ${charter[14]:,.2f}' if charter[14] else 'Paid Amount: NULL')
        print(f'Total Due: ${charter[15]:,.2f}' if charter[15] else 'Total Due: NULL')
        print(f'\nSTATUS:')
        print(f'Status: {charter[16]}')
        print(f'Closed: {charter[17]}')
        print(f'\nASSIGNMENTS:')
        print(f'Vehicle: {charter[18]}')
        print(f'Driver: {charter[19]}')
        print(f'\nLOCATIONS:')
        print(f'Pickup: {charter[20]}')
        print(f'Dropoff: {charter[21]}')
        print(f'\nMILEAGE:')
        print(f'Odometer Start: {charter[22]}')
        print(f'Odometer End: {charter[23]}')
        print(f'Total KMs: {charter[24]}')
        print(f'\nCLIENT:')
        print(f'Name: {charter[25]}')
        print(f'Email: {charter[26]}')
        if charter[27]:
            print(f'\nNOTES:')
            print(charter[27])
        
        charter_id = charter[0]
    else:
        print('\n[FAIL] Charter not found!')
        cur.close()
        conn.close()
        return

    # Check if there's a charter in 2018 that might match
    print('\n\n' + '=' * 80)
    print('CHECKING FOR 2018 CHARTER - MAY 16, 2018')
    print('=' * 80)

    cur.execute("""
        SELECT 
            c.charter_id,
            c.reserve_number,
            c.charter_date,
            c.pickup_time,
            c.actual_start_time,
            c.actual_end_time,
            c.rate,
            c.balance,
            c.closed,
            cl.client_name
        FROM charters c
        LEFT JOIN clients cl ON c.client_id = cl.client_id
        WHERE c.charter_date BETWEEN '2018-05-15' AND '2018-05-17'
          AND (LOWER(cl.client_name) LIKE '%holly%' 
               OR LOWER(cl.client_name) LIKE '%graham%')
    """)

    may2018_charters = cur.fetchall()
    if may2018_charters:
        print(f'\n[OK] Found {len(may2018_charters)} charter(s) for Holly Graham on May 16, 2018:')
        for ch in may2018_charters:
            print(f'\n  Charter ID: {ch[0]}')
            print(f'  Reserve: {ch[1]}')
            print(f'  Date: {ch[2]}')
            print(f'  Pickup Time: {ch[3]}')
            print(f'  Start: {ch[4]}')
            print(f'  End: {ch[5]}')
            print(f'  Rate: ${ch[6]:,.2f}' if ch[6] else '  Rate: NULL')
            print(f'  Balance: ${ch[7]:,.2f}' if ch[7] else '  Balance: NULL')
            print(f'  Closed: {ch[8]}')
            print(f'  Client: {ch[9]}')
    else:
        print('\n[FAIL] NO charter found for Holly Graham on May 16, 2018!')
        print('This suggests the Square receipt date May 16, 2018 may be INCORRECT.')

    # Check all Holly Graham charters
    print('\n\n' + '=' * 80)
    print('ALL HOLLY GRAHAM CHARTERS')
    print('=' * 80)

    cur.execute("""
        SELECT 
            c.charter_id,
            c.reserve_number,
            c.charter_date,
            c.pickup_time,
            c.rate,
            c.balance,
            c.closed,
            c.vehicle,
            c.total_kms
        FROM charters c
        LEFT JOIN clients cl ON c.client_id = cl.client_id
        WHERE LOWER(cl.client_name) LIKE '%holly%'
           OR LOWER(cl.client_name) LIKE '%graham%'
        ORDER BY c.charter_date DESC
    """)

    all_charters = cur.fetchall()
    print(f'\nFound {len(all_charters)} total charter(s) for Holly/Graham:\n')
    
    for ch in all_charters:
        balance_status = '[OK] PAID' if ch[5] == 0 else f'[FAIL] OWES ${ch[5]:,.2f}'
        kms = f'{ch[8]} km' if ch[8] else 'No mileage'
        print(f'{ch[1]} | {ch[2]} {ch[3]} | ${ch[4]:,.2f} | {balance_status} | Vehicle {ch[7]} | {kms}')

    cur.close()
    conn.close()

    print('\n\n' + '=' * 80)
    print('ANALYSIS & CONCLUSION:')
    print('=' * 80)
    print('Square Receipt Details:')
    print('  Date: Wednesday, May 16, 2018')
    print('  Time: 7:00 AM - 7:30 PM MDT (12.5 hours)')
    print('  Amount: $1,417.20')
    print('')
    print('Charter 015808 Details:')
    print('  Date: Saturday, June 26, 2021')
    print('  Time: 10:00 AM pickup')
    print('  Rate: $181.00')
    print('  Balance: $1,417.20 (UNPAID)')
    print('  Vehicle: L-23')
    print('  Booking Email: June 25, 2021 "L23 holly Graham"')
    print('')
    print('❓ POSSIBLE EXPLANATIONS:')
    print('  1. Square receipt date is WRONG (2018 vs 2021 = 3 year difference)')
    print('  2. May 16, 2018 charter does NOT exist in database')
    print('  3. The $1,417.20 payment is for charter 015808 (June 26, 2021)')
    print('  4. User/Square system may have displayed wrong date')
    print('')
    print('🎯 RECOMMENDED ACTION:')
    print('  - Find the Square payment with amount $1,417.20')
    print('  - Check the actual payment date in database')
    print('  - Link it to charter 015808 (charter_id = 14698)')
    print('  - This will resolve the $1,417.20 balance')

if __name__ == '__main__':
    main()
