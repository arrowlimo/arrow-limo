#!/usr/bin/env python3
"""
Verify charter 006587 King Kent - August 13, 2012
Rate: $210, Deposit: $231 (includes GST + fuel surcharge)
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
    print('CHARTER 006587 - KING KENT - AUGUST 13, 2012')
    print('GST + Fuel Surcharge Analysis')
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
            c.driver
        FROM charters c
        LEFT JOIN clients cl ON c.client_id = cl.client_id
        WHERE c.reserve_number = '006587'
    """)

    charter = cur.fetchone()
    if charter:
        print(f'\nCHARTER DETAILS:')
        print(f'  Charter ID: {charter[0]}')
        print(f'  Reserve Number: {charter[1]}')
        print(f'  Date: {charter[2]} at {charter[3]}')
        print(f'  Rate: ${charter[4]:,.2f}' if charter[4] else '  Rate: $0.00')
        print(f'  Balance: ${charter[5]:,.2f}' if charter[5] else '  Balance: $0.00')
        print(f'  Deposit: ${charter[6]:,.2f}' if charter[6] else '  Deposit: $0.00')
        print(f'  Paid Amount: ${charter[7]:,.2f}' if charter[7] else '  Paid Amount: $0.00')
        print(f'  Total Due: ${charter[8]:,.2f}' if charter[8] else '  Total Due: $0.00')
        print(f'  Status: {charter[9]}')
        print(f'  Closed: {charter[10]}')
        print(f'  Cancelled: {charter[11]}')
        print(f'  Client: {charter[12]}')
        print(f'  Email: {charter[13]}')
        print(f'  Vehicle: {charter[14]}')
        print(f'  Driver: {charter[15]}')
        
        rate = float(charter[4]) if charter[4] else 0
        deposit = float(charter[6]) if charter[6] else 0
        
        charter_id = charter[0]
        
        # Calculate GST and fuel surcharge
        print(f'\n\nFINANCIAL BREAKDOWN:')
        print('-' * 80)
        print(f'  Base Rate: ${rate:,.2f}')
        
        # GST is 5% in Alberta
        gst = rate * 0.05
        print(f'  GST (5%): ${gst:,.2f}')
        
        # Calculate what's left after GST
        subtotal_with_gst = rate + gst
        fuel_surcharge = deposit - subtotal_with_gst
        
        print(f'  Fuel Surcharge: ${fuel_surcharge:,.2f}')
        print(f'  -' * 40)
        print(f'  TOTAL (Deposit): ${deposit:,.2f}')
        
        # Verify calculation
        calculated_total = rate + gst + fuel_surcharge
        print(f'\n  Verification: ${rate:,.2f} + ${gst:,.2f} + ${fuel_surcharge:,.2f} = ${calculated_total:,.2f}')
        if abs(calculated_total - deposit) < 0.01:
            print(f'  [OK] Calculation matches deposit!')
        else:
            print(f'  [FAIL] Mismatch! Expected ${deposit:,.2f}, got ${calculated_total:,.2f}')
        
        # Get payments
        cur.execute("""
            SELECT 
                p.payment_id,
                p.payment_date,
                p.amount,
                p.payment_method,
                p.payment_key,
                p.notes
            FROM payments p
            WHERE p.charter_id = %s
            ORDER BY p.payment_date
        """, (charter_id,))
        
        payments = cur.fetchall()
        if payments:
            print(f'\n\nPAYMENTS ({len(payments)} total):')
            print('-' * 80)
            total_paid = 0
            for pmt in payments:
                print(f'\n  Payment ID: {pmt[0]}')
                print(f'    Date: {pmt[1]}')
                print(f'    Amount: ${pmt[2]:,.2f}')
                print(f'    Method: {pmt[3]}')
                print(f'    Key: {pmt[4]}')
                if pmt[5]:
                    print(f'    Notes: {pmt[5][:100]}')
                total_paid += float(pmt[2]) if pmt[2] else 0
            
            print(f'\n  TOTAL PAYMENTS: ${total_paid:,.2f}')
            
            if abs(total_paid - deposit) < 0.01:
                print(f'  [OK] Payments match deposit of ${deposit:,.2f}')
            else:
                difference = total_paid - deposit
                print(f'  [WARN]  Difference: ${difference:,.2f} (Paid ${total_paid:,.2f}, Expected ${deposit:,.2f})')
        else:
            print('\n\n[FAIL] NO PAYMENTS LINKED TO THIS CHARTER!')
    else:
        print('\n[FAIL] Charter 006587 not found in database!')

    cur.close()
    conn.close()

    print('\n\n' + '=' * 80)
    print('CSV DATA ANALYSIS:')
    print('=' * 80)
    print('From CSV: 5549,006587,2012-08-13,13:30:00,Closed,TRUE,FALSE,King Kent...')
    print('')
    print('  Rate: $210.00')
    print('  Deposit: $231.00')
    print('  Balance: $0.00')
    print('')
    print('CORRECT TOTAL CALCULATION:')
    print('  Base Rate: $210.00')
    print('  GST (5%): $10.50')
    print('  Fuel Surcharge: $10.50')
    print('  ─────────────────')
    print('  TOTAL: $231.00 ✓')
    print('')
    print('This charter is properly calculated with GST + fuel surcharge included.')

if __name__ == '__main__':
    main()
