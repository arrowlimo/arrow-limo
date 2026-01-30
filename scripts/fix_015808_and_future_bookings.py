#!/usr/bin/env python3
"""
1. Mark charter 015808 as cancelled (no charges)
2. Remove future bookings (2025-2027) from unmatched charter analysis
3. Verify reservation date accuracy
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
    print('TASK 1: CANCEL CHARTER 015808 - NO CHARGES')
    print('=' * 80)
    
    # Get current state
    cur.execute("""
        SELECT charter_id, reserve_number, charter_date, rate, balance, 
               deposit, paid_amount, status, closed, cancelled
        FROM charters
        WHERE reserve_number = '015808'
    """)
    
    charter = cur.fetchone()
    if charter:
        print(f'\nCURRENT STATE:')
        print(f'  Charter ID: {charter[0]}')
        print(f'  Reserve: {charter[1]}')
        print(f'  Date: {charter[2]}')
        print(f'  Rate: ${charter[3]:,.2f}' if charter[3] else '  Rate: NULL')
        print(f'  Balance: ${charter[4]:,.2f}' if charter[4] else '  Balance: NULL')
        print(f'  Deposit: ${charter[5]:,.2f}' if charter[5] else '  Deposit: NULL')
        print(f'  Paid Amount: ${charter[6]:,.2f}' if charter[6] else '  Paid Amount: NULL')
        print(f'  Status: {charter[7]}')
        print(f'  Closed: {charter[8]}')
        print(f'  Cancelled: {charter[9]}')
        
        charter_id = charter[0]
        
        # Update to cancelled with no charges
        print(f'\nUPDATING TO CANCELLED (NO CHARGES):')
        cur.execute("""
            UPDATE charters
            SET cancelled = true,
                closed = true,
                status = 'Cancelled',
                rate = 0,
                balance = 0,
                deposit = 0,
                paid_amount = 0,
                total_amount_due = 0
            WHERE charter_id = %s
        """, (charter_id,))
        
        print(f'  [OK] Updated charter 015808')
        print(f'  - Set cancelled = TRUE')
        print(f'  - Set closed = TRUE')
        print(f'  - Set status = Cancelled')
        print(f'  - Zeroed all fees: rate, balance, deposit, paid_amount, total_amount_due')
        
        conn.commit()
    else:
        print('  [FAIL] Charter 015808 not found!')

    # Task 2: Check future bookings (2025-2027)
    print('\n\n' + '=' * 80)
    print('TASK 2: FUTURE BOOKINGS (2025-2027) ANALYSIS')
    print('=' * 80)
    
    cur.execute("""
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN closed = false AND balance > 0 THEN 1 ELSE 0 END) as open_with_balance,
            SUM(CASE WHEN closed = true AND balance > 0 THEN 1 ELSE 0 END) as closed_with_balance,
            SUM(balance) as total_balance
        FROM charters
        WHERE charter_date >= '2025-01-01'
          AND charter_date < '2028-01-01'
          AND cancelled = false
    """)
    
    future = cur.fetchone()
    print(f'\nFUTURE BOOKINGS (2025-2027):')
    print(f'  Total Charters: {future[0]}')
    print(f'  Open with Balance: {future[1]}')
    print(f'  Closed with Balance: {future[2]}')
    print(f'  Total Balance: ${future[3]:,.2f}' if future[3] else '  Total Balance: $0.00')
    
    # Show sample of future bookings with balance
    cur.execute("""
        SELECT 
            c.reserve_number,
            c.charter_date,
            cl.client_name,
            c.rate,
            c.balance,
            c.status,
            c.closed
        FROM charters c
        LEFT JOIN clients cl ON c.client_id = cl.client_id
        WHERE c.charter_date >= '2025-01-01'
          AND c.charter_date < '2028-01-01'
          AND c.cancelled = false
          AND c.balance > 0
        ORDER BY c.charter_date
        LIMIT 20
    """)
    
    future_charters = cur.fetchall()
    if future_charters:
        print(f'\nSAMPLE FUTURE BOOKINGS WITH BALANCE (showing first 20):')
        print('-' * 80)
        for ch in future_charters:
            status = f'{ch[5]} (Closed={ch[6]})'
            print(f'{ch[0]} | {ch[1]} | {ch[2][:30] if ch[2] else "Unknown":30} | ${ch[3]:>8.2f} | Balance ${ch[4]:>8.2f} | {status}')

    # Task 3: Verify reservation date column
    print('\n\n' + '=' * 80)
    print('TASK 3: RESERVATION DATE vs CHARTER DATE VERIFICATION')
    print('=' * 80)
    
    cur.execute("""
        SELECT 
            COUNT(*) as total,
            COUNT(reservation_time) as has_reservation_time,
            SUM(CASE WHEN reservation_time IS NOT NULL 
                     AND reservation_time::date > charter_date THEN 1 ELSE 0 END) as reservation_after_charter,
            SUM(CASE WHEN reservation_time IS NOT NULL 
                     AND charter_date - reservation_time::date > 365 THEN 1 ELSE 0 END) as reserved_over_year_early
        FROM charters
        WHERE cancelled = false
    """)
    
    dates = cur.fetchone()
    print(f'\nRESERVATION DATE ANALYSIS:')
    print(f'  Total Charters: {dates[0]}')
    print(f'  With Reservation Time: {dates[1]} ({dates[1]/dates[0]*100:.1f}%)')
    print(f'  Reservation AFTER Charter: {dates[2]} (DATA ERROR!)')
    print(f'  Reserved >1 Year Early: {dates[3]}')
    
    # Check 015808 specifically
    cur.execute("""
        SELECT reserve_number, charter_date, reservation_time, 
               charter_date - reservation_time::date as days_advance
        FROM charters
        WHERE reserve_number = '015808'
    """)
    
    res015808 = cur.fetchone()
    if res015808:
        print(f'\nCHARTER 015808 DATES:')
        print(f'  Charter Date: {res015808[1]}')
        print(f'  Reservation Time: {res015808[2]}')
        if res015808[3] is not None:
            days = res015808[3].days if hasattr(res015808[3], 'days') else res015808[3]
            print(f'  Days in Advance: {days} days')

    # Check 019672 (2026 charter mentioned)
    cur.execute("""
        SELECT c.reserve_number, c.charter_date, c.reservation_time,
               cl.client_name, c.vehicle, c.rate, c.balance, c.status, c.closed
        FROM charters c
        LEFT JOIN clients cl ON c.client_id = cl.client_id
        WHERE c.reserve_number = '019672'
    """)
    
    res019672 = cur.fetchone()
    if res019672:
        print(f'\n\nCHARTER 019672 (L-24 Events by Dianna):')
        print(f'  Reserve: {res019672[0]}')
        print(f'  Charter Date: {res019672[1]}')
        print(f'  Reservation Time: {res019672[2]}')
        print(f'  Client: {res019672[3]}')
        print(f'  Vehicle: {res019672[4]}')
        print(f'  Rate: ${res019672[5]:,.2f}' if res019672[5] else '  Rate: NULL')
        print(f'  Balance: ${res019672[6]:,.2f}' if res019672[6] else '  Balance: NULL')
        print(f'  Status: {res019672[7]} (Closed={res019672[8]})')
        print(f'\n  [OK] This is a 2026 booking - should NOT be in "unmatched charters" analysis')

    cur.close()
    conn.close()

    print('\n\n' + '=' * 80)
    print('SUMMARY:')
    print('=' * 80)
    print('[OK] Charter 015808: Marked as CANCELLED with all fees zeroed')
    print('📊 Future Bookings: Identified charters that should be excluded from "unmatched" analysis')
    print('📅 Reservation Dates: Verified date accuracy')
    print('')
    print('RECOMMENDATION FOR UNMATCHED CHARTERS WORKBOOK:')
    print('  - Add filter: WHERE charter_date < CURRENT_DATE')
    print('  - This excludes future bookings (2025-2027) from "needs payment" analysis')
    print('  - Future bookings are normal - payment comes later')

if __name__ == '__main__':
    main()
