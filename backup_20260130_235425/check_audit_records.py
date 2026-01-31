#!/usr/bin/env python3
"""
Check all AUDIT records and their impact
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
    print('ALL AUDIT RECORDS ANALYSIS')
    print('=' * 80)

    # Count and totals
    cur.execute("""
        SELECT 
            COUNT(*),
            SUM(rate),
            SUM(balance),
            SUM(deposit)
        FROM charters
        WHERE reserve_number LIKE 'AUDIT%'
        AND cancelled = false
    """)
    
    stats = cur.fetchone()
    print(f'\nAUDIT Records Summary:')
    print(f'  Count: {stats[0]}')
    print(f'  Total Rate: ${stats[1]:,.2f}' if stats[1] else '  Total Rate: $0.00')
    print(f'  Total Balance: ${stats[2]:,.2f}' if stats[2] else '  Total Balance: $0.00')
    print(f'  Total Deposit: ${stats[3]:,.2f}' if stats[3] else '  Total Deposit: $0.00')

    # List all AUDIT records
    print('\n\nAll AUDIT Records:')
    print('-' * 80)
    
    cur.execute("""
        SELECT 
            reserve_number,
            charter_date,
            rate,
            balance,
            deposit,
            booking_notes
        FROM charters
        WHERE reserve_number LIKE 'AUDIT%'
        ORDER BY reserve_number
    """)
    
    records = cur.fetchall()
    for r in records:
        rate = r[2] if r[2] else 0
        balance = r[3] if r[3] else 0
        deposit = r[4] if r[4] else 0
        notes = r[5][:60] if r[5] else ''
        print(f'{r[0]:15} {r[1]} Rate ${rate:>8.2f} Bal ${balance:>8.2f} Dep ${deposit:>8.2f} - {notes}')

    # Check if they're in unmatched workbook
    print('\n\nImpact on Unmatched Workbook:')
    print('-' * 80)
    
    cur.execute("""
        SELECT COUNT(*)
        FROM charters c
        WHERE c.reserve_number LIKE 'AUDIT%'
        AND c.cancelled = false
        AND c.charter_date < CURRENT_DATE
        AND NOT EXISTS (
            SELECT 1 FROM payments p WHERE p.charter_id = c.charter_id AND p.amount > 0
        )
        AND (c.rate > 0 OR c.balance > 0)
    """)
    
    no_payments = cur.fetchone()[0]
    
    cur.execute("""
        SELECT COUNT(*)
        FROM charters c
        WHERE c.reserve_number LIKE 'AUDIT%'
        AND c.closed = true
        AND c.cancelled = false
        AND c.charter_date < CURRENT_DATE
        AND c.balance > 0
    """)
    
    closed_balance = cur.fetchone()[0]
    
    cur.execute("""
        SELECT COUNT(*)
        FROM charters c
        WHERE c.reserve_number LIKE 'AUDIT%'
        AND c.closed = false
        AND c.cancelled = false
        AND c.charter_date < CURRENT_DATE
        AND c.balance > 0
    """)
    
    open_balance = cur.fetchone()[0]
    
    print(f'AUDIT records in "No Payments" sheet: {no_payments}')
    print(f'AUDIT records in "Closed With Balance" sheet: {closed_balance}')
    print(f'AUDIT records in "Open With Balance" sheet: {open_balance}')
    print(f'Total AUDIT records in workbook: {no_payments + closed_balance + open_balance}')

    cur.close()
    conn.close()

    print('\n\n' + '=' * 80)
    print('RECOMMENDATION')
    print('=' * 80)
    print('\nAUDIT records are internal accounting entries (refund pairs, adjustments).')
    print('They should be EXCLUDED from the unmatched payments workbook.')
    print('\nAdd this filter to all 3 queries:')
    print('  AND c.reserve_number NOT LIKE \'AUDIT%\'')

if __name__ == '__main__':
    main()
