#!/usr/bin/env python3
"""
Investigate charter AUDIT003379 and fix missing data
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
    print('CHARTER AUDIT003379 INVESTIGATION')
    print('=' * 80)

    # Get full charter details
    cur.execute("""
        SELECT 
            c.charter_id,
            c.reserve_number,
            c.charter_date,
            c.pickup_time,
            c.status,
            c.closed,
            c.cancelled,
            c.client_id,
            cl.client_name,
            c.rate,
            c.balance,
            c.deposit,
            c.driver_gratuity,
            c.pickup_address,
            c.dropoff_address,
            c.notes,
            c.booking_notes
        FROM charters c
        LEFT JOIN clients cl ON c.client_id = cl.client_id
        WHERE c.reserve_number = 'AUDIT003379'
    """)
    
    charter = cur.fetchone()
    
    if not charter:
        print('✗ Charter AUDIT003379 not found!')
        cur.close()
        conn.close()
        return
    
    print('\nCHARTER DETAILS:')
    print('-' * 80)
    print(f'Charter ID: {charter[0]}')
    print(f'Reserve Number: {charter[1]}')
    print(f'Date: {charter[2]}')
    print(f'Pickup Time: {charter[3]}')
    print(f'Status: {charter[4]}')
    print(f'Closed: {charter[5]}')
    print(f'Cancelled: {charter[6]}')
    print(f'Client ID: {charter[7]}')
    print(f'Client Name: {charter[8]}')
    print(f'Rate: ${charter[9]:.2f}' if charter[9] else 'NULL')
    print(f'Balance: ${charter[10]:.2f}' if charter[10] else 'NULL')
    print(f'Deposit: ${charter[11]:.2f}' if charter[11] else 'NULL')
    print(f'Gratuity: ${charter[12]:.2f}' if charter[12] else 'NULL')
    print(f'Pickup Address: {charter[13]}')
    print(f'Dropoff Address: {charter[14]}')
    print(f'Notes: {charter[15]}')
    print(f'Booking Notes: {charter[16]}')

    # Check charter_charges
    print('\n\nCHARTER_CHARGES:')
    print('-' * 80)
    
    cur.execute("""
        SELECT 
            charge_id,
            charge_type,
            amount,
            description
        FROM charter_charges
        WHERE charter_id = %s
        ORDER BY charge_id
    """, (charter[0],))
    
    charges = cur.fetchall()
    if charges:
        total_charges = 0
        for c in charges:
            print(f'  Charge {c[0]}: {c[1]:20} ${c[2]:>8.2f} - {c[3]}')
            if c[1] != 'customer_tip':
                total_charges += c[2]
        print(f'\nTotal Billable Charges: ${total_charges:.2f}')
    else:
        print('  No charges found')

    # Check payments
    print('\n\nPAYMENTS:')
    print('-' * 80)
    
    cur.execute("""
        SELECT 
            payment_id,
            payment_date,
            amount,
            payment_method,
            notes
        FROM payments
        WHERE charter_id = %s
        ORDER BY payment_date
    """, (charter[0],))
    
    payments = cur.fetchall()
    if payments:
        total_payments = 0
        for p in payments:
            print(f'  Payment {p[0]}: {p[1]} ${p[2]:>8.2f} ({p[3]}) - {p[4] if p[4] else ""}')
            total_payments += p[2]
        print(f'\nTotal Payments: ${total_payments:.2f}')
    else:
        print('  No payments found')

    # Check for related AUDIT records
    print('\n\nRELATED AUDIT RECORDS:')
    print('-' * 80)
    
    cur.execute("""
        SELECT 
            charter_id,
            reserve_number,
            charter_date,
            rate,
            balance,
            deposit,
            notes
        FROM charters
        WHERE reserve_number LIKE 'AUDIT00%'
        AND (reserve_number = 'AUDIT003379' OR reserve_number = 'AUDIT003634')
        ORDER BY reserve_number
    """)
    
    audit_records = cur.fetchall()
    for ar in audit_records:
        print(f'\n  {ar[1]} (charter_id {ar[0]}):')
        print(f'    Date: {ar[2]}')
        print(f'    Rate: ${ar[3]:.2f}' if ar[3] else 'NULL')
        print(f'    Balance: ${ar[4]:.2f}' if ar[4] else 'NULL')
        print(f'    Deposit: ${ar[5]:.2f}' if ar[5] else 'NULL')
        print(f'    Notes: {ar[6]}')

    # Check if this is a refund pair
    print('\n\n' + '=' * 80)
    print('ANALYSIS')
    print('=' * 80)
    
    if 'Refund pair' in str(charter[16]):
        print('\n✓ This is a REFUND PAIR record')
        print('  Notes indicate: "AUDIT: Refund pair 3379/3634"')
        print('\nREFUND PAIRS are audit records for offsetting entries:')
        print('  - One record shows the original charge')
        print('  - The other shows the refund/reversal')
        print('  - Net effect should be $0')
        
        # Calculate net effect
        rate = charter[9] if charter[9] else 0
        balance = charter[10] if charter[10] else 0
        deposit = charter[11] if charter[11] else 0
        
        print(f'\nThis record:')
        print(f'  Rate: ${rate:.2f}')
        print(f'  Balance: ${balance:.2f}')
        print(f'  Deposit: ${deposit:.2f}')
        
        # Get the pair
        cur.execute("""
            SELECT rate, balance, deposit
            FROM charters
            WHERE reserve_number = 'AUDIT003634'
        """)
        pair = cur.fetchone()
        if pair:
            print(f'\nPair record (AUDIT003634):')
            print(f'  Rate: ${pair[0]:.2f}' if pair[0] else 'NULL')
            print(f'  Balance: ${pair[1]:.2f}' if pair[1] else 'NULL')
            print(f'  Deposit: ${pair[2]:.2f}' if pair[2] else 'NULL')
            
            net_rate = rate + (pair[0] if pair[0] else 0)
            net_balance = balance + (pair[1] if pair[1] else 0)
            net_deposit = deposit + (pair[2] if pair[2] else 0)
            
            print(f'\nNet effect:')
            print(f'  Rate: ${net_rate:.2f}')
            print(f'  Balance: ${net_balance:.2f}')
            print(f'  Deposit: ${net_deposit:.2f}')
            
            if abs(net_rate) < 0.01 and abs(net_balance) < 0.01 and abs(net_deposit) < 0.01:
                print('\n✓ Refund pair balances correctly to $0')
            else:
                print('\n[WARN]  Refund pair does NOT balance!')
        
        print('\nRECOMMENDATION:')
        print('  Exclude AUDIT records from unmatched payments workbook')
        print('  Add filter: WHERE reserve_number NOT LIKE \'AUDIT%\'')

    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
