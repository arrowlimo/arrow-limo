#!/usr/bin/env python3
"""
Compare LMS Access database totals vs PostgreSQL to find discrepancies
"""

import pyodbc
import psycopg2
import os

LMS_PATH = r'L:\limo\backups\lms.mdb'

def get_lms_connection():
    conn_str = f'DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={LMS_PATH};'
    return pyodbc.connect(conn_str)

def get_pg_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***')
    )

def main():
    print('=' * 100)
    print('LMS vs POSTGRESQL COMPARISON')
    print('=' * 100)

    lms_conn = get_lms_connection()
    pg_conn = get_pg_connection()
    
    lms_cur = lms_conn.cursor()
    pg_cur = pg_conn.cursor()

    # LMS Reserve table analysis
    print('\nLMS RESERVE TABLE:')
    print('-' * 100)
    
    lms_cur.execute("""
        SELECT 
            COUNT(*) as total,
            SUM(IIF(Rate IS NOT NULL, 1, 0)) as with_rate,
            SUM(IIF(Balance IS NOT NULL, 1, 0)) as with_balance,
            SUM(IIF(Deposit IS NOT NULL, 1, 0)) as with_deposit,
            SUM(Rate) as total_rate,
            SUM(Balance) as total_balance,
            SUM(Deposit) as total_deposit
        FROM Reserve
    """)
    
    lms_stats = lms_cur.fetchone()
    print(f'Total Reserves: {lms_stats[0]:,}')
    print(f'With Rate: {lms_stats[1]:,} ({lms_stats[1]/lms_stats[0]*100:.1f}%)')
    print(f'With Balance: {lms_stats[2]:,} ({lms_stats[2]/lms_stats[0]*100:.1f}%)')
    print(f'With Deposit: {lms_stats[3]:,} ({lms_stats[3]/lms_stats[0]*100:.1f}%)')
    print()
    print(f'Total Rate: ${lms_stats[4]:,.2f}' if lms_stats[4] else 'NULL')
    print(f'Total Balance: ${lms_stats[5]:,.2f}' if lms_stats[5] else 'NULL')
    print(f'Total Deposit: ${lms_stats[6]:,.2f}' if lms_stats[6] else 'NULL')

    # LMS Payment table analysis
    print('\n\nLMS PAYMENT TABLE:')
    print('-' * 100)
    
    lms_cur.execute("""
        SELECT 
            COUNT(*) as total,
            SUM(Amount) as total_amount,
            SUM(IIF(Amount > 0, 1, 0)) as positive_payments,
            SUM(IIF(Amount > 0, Amount, 0)) as positive_total,
            SUM(IIF(Amount < 0, 1, 0)) as negative_payments,
            SUM(IIF(Amount < 0, Amount, 0)) as negative_total
        FROM Payment
    """)
    
    lms_payments = lms_cur.fetchone()
    print(f'Total Payments: {lms_payments[0]:,}')
    print(f'Total Payment Amount: ${lms_payments[1]:,.2f}' if lms_payments[1] else 'NULL')
    print(f'Positive Payments: {lms_payments[2]:,} (${lms_payments[3]:,.2f})' if lms_payments[2] else 'None')
    print(f'Negative Payments: {lms_payments[4]:,} (${lms_payments[5]:,.2f})' if lms_payments[4] else 'None')

    # PostgreSQL charters analysis
    print('\n\nPOSTGRESQL CHARTERS TABLE:')
    print('-' * 100)
    
    pg_cur.execute("""
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN rate IS NOT NULL THEN 1 ELSE 0 END) as with_rate,
            SUM(CASE WHEN balance IS NOT NULL THEN 1 ELSE 0 END) as with_balance,
            SUM(CASE WHEN deposit IS NOT NULL THEN 1 ELSE 0 END) as with_deposit,
            SUM(rate) as total_rate,
            SUM(balance) as total_balance,
            SUM(deposit) as total_deposit,
            SUM(driver_gratuity) as total_gratuity
        FROM charters
        WHERE cancelled = false
    """)
    
    pg_stats = pg_cur.fetchone()
    print(f'Total Charters: {pg_stats[0]:,}')
    print(f'With Rate: {pg_stats[1]:,} ({pg_stats[1]/pg_stats[0]*100:.1f}%)')
    print(f'With Balance: {pg_stats[2]:,} ({pg_stats[2]/pg_stats[0]*100:.1f}%)')
    print(f'With Deposit: {pg_stats[3]:,} ({pg_stats[3]/pg_stats[0]*100:.1f}%)')
    print()
    print(f'Total Rate: ${pg_stats[4]:,.2f}' if pg_stats[4] else 'NULL')
    print(f'Total Balance: ${pg_stats[5]:,.2f}' if pg_stats[5] else 'NULL')
    print(f'Total Deposit: ${pg_stats[6]:,.2f}' if pg_stats[6] else 'NULL')
    print(f'Total Gratuity: ${pg_stats[7]:,.2f}' if pg_stats[7] else 'NULL')

    # PostgreSQL charter_charges analysis
    print('\n\nPOSTGRESQL CHARTER_CHARGES TABLE:')
    print('-' * 100)
    
    pg_cur.execute("""
        SELECT 
            COUNT(*) as total,
            SUM(amount) as total_amount,
            SUM(CASE WHEN charge_type = 'customer_tip' THEN amount ELSE 0 END) as tips,
            SUM(CASE WHEN charge_type != 'customer_tip' THEN amount ELSE 0 END) as billable
        FROM charter_charges
    """)
    
    pg_charges = pg_cur.fetchone()
    print(f'Total Charges: {pg_charges[0]:,}')
    print(f'Total Amount: ${pg_charges[1]:,.2f}' if pg_charges[1] else 'NULL')
    print(f'Customer Tips: ${pg_charges[2]:,.2f}')
    print(f'Billable Charges: ${pg_charges[3]:,.2f}')

    # PostgreSQL payments analysis
    print('\n\nPOSTGRESQL PAYMENTS TABLE:')
    print('-' * 100)
    
    pg_cur.execute("""
        SELECT 
            COUNT(*) as total,
            SUM(amount) as total_amount,
            SUM(CASE WHEN amount > 0 THEN 1 ELSE 0 END) as positive_payments,
            SUM(CASE WHEN amount > 0 THEN amount ELSE 0 END) as positive_total,
            SUM(CASE WHEN amount < 0 THEN 1 ELSE 0 END) as negative_payments,
            SUM(CASE WHEN amount < 0 THEN amount ELSE 0 END) as negative_total
        FROM payments
    """)
    
    pg_payments = pg_cur.fetchone()
    print(f'Total Payments: {pg_payments[0]:,}')
    print(f'Total Payment Amount: ${pg_payments[1]:,.2f}' if pg_payments[1] else 'NULL')
    print(f'Positive Payments: {pg_payments[2]:,} (${pg_payments[3]:,.2f})' if pg_payments[2] else 'None')
    print(f'Negative Payments: {pg_payments[4]:,} (${pg_payments[5]:,.2f})' if pg_payments[4] else 'None')

    # Sample comparison - specific reserves
    print('\n\n' + '=' * 100)
    print('SAMPLE RESERVES - LMS vs POSTGRESQL COMPARISON')
    print('=' * 100)
    
    lms_cur.execute("""
        SELECT TOP 10
            Reserve_No,
            Rate,
            Balance,
            Deposit
        FROM Reserve
        ORDER BY Reserve_No DESC
    """)
    
    lms_samples = lms_cur.fetchall()
    
    print('\nLatest 10 Reserves:')
    print(f'{"Reserve":10} {"LMS Rate":>12} {"LMS Balance":>12} {"LMS Deposit":>12} | {"PG Rate":>12} {"PG Balance":>12} {"PG Deposit":>12} {"PG Gratuity":>12} {"PG Charges":>12}')
    print('-' * 140)
    
    for lms in lms_samples:
        reserve = lms[0]
        lms_rate = lms[1] if lms[1] else 0
        lms_balance = lms[2] if lms[2] else 0
        lms_deposit = lms[3] if lms[3] else 0
        
        # Get PG data
        pg_cur.execute("""
            SELECT 
                c.rate,
                c.balance,
                c.deposit,
                c.driver_gratuity,
                COALESCE(
                    (SELECT SUM(amount) 
                     FROM charter_charges cc 
                     WHERE cc.charter_id = c.charter_id 
                     AND cc.charge_type != 'customer_tip'),
                    0
                )
            FROM charters c
            WHERE c.reserve_number = %s
        """, (reserve,))
        
        pg_row = pg_cur.fetchone()
        if pg_row:
            pg_rate = pg_row[0] if pg_row[0] else 0
            pg_balance = pg_row[1] if pg_row[1] else 0
            pg_deposit = pg_row[2] if pg_row[2] else 0
            pg_gratuity = pg_row[3] if pg_row[3] else 0
            pg_charges = pg_row[4]
            
            rate_match = '✓' if abs(lms_rate - pg_rate) < 0.01 else '✗'
            deposit_match = '✓' if abs(lms_deposit - pg_deposit) < 0.01 else '✗'
            
            print(f'{reserve:10} ${lms_rate:>11.2f} ${lms_balance:>11.2f} ${lms_deposit:>11.2f} | ${pg_rate:>11.2f}{rate_match} ${pg_balance:>11.2f} ${pg_deposit:>11.2f}{deposit_match} ${pg_gratuity:>11.2f} ${pg_charges:>11.2f}')
        else:
            print(f'{reserve:10} ${lms_rate:>11.2f} ${lms_balance:>11.2f} ${lms_deposit:>11.2f} | NOT FOUND IN POSTGRESQL')

    # CRITICAL: Check total invoice calculation
    print('\n\n' + '=' * 100)
    print('INVOICE TOTAL CALCULATION COMPARISON')
    print('=' * 100)
    
    print('\nLMS CALCULATION:')
    print('  Invoice Total = Rate (that\'s it - no separate GST/charges table)')
    print(f'  Total Rate: ${lms_stats[4]:,.2f}')
    
    print('\nPOSTGRESQL CALCULATION:')
    print('  Invoice Total = Rate + Gratuity + Charter_Charges')
    pg_cur.execute("""
        SELECT 
            SUM(c.rate) as total_rate,
            SUM(c.driver_gratuity) as total_gratuity,
            SUM(COALESCE(
                (SELECT SUM(amount) 
                 FROM charter_charges cc 
                 WHERE cc.charter_id = c.charter_id 
                 AND cc.charge_type != 'customer_tip'),
                0
            )) as total_charges,
            SUM(c.rate + COALESCE(c.driver_gratuity, 0) + COALESCE(
                (SELECT SUM(amount) 
                 FROM charter_charges cc 
                 WHERE cc.charter_id = c.charter_id 
                 AND cc.charge_type != 'customer_tip'),
                0
            )) as total_invoice
        FROM charters c
        WHERE c.cancelled = false
    """)
    
    pg_invoice = pg_cur.fetchone()
    print(f'  Total Rate: ${pg_invoice[0]:,.2f}')
    print(f'  Total Gratuity: ${pg_invoice[1]:,.2f}')
    print(f'  Total Charges: ${pg_invoice[2]:,.2f}')
    print(f'  TOTAL INVOICE: ${pg_invoice[3]:,.2f}')
    
    print(f'\nDIFFERENCE: ${pg_invoice[3] - lms_stats[4]:,.2f}')
    print(f'  = Gratuity (${pg_invoice[1]:,.2f}) + Charges (${pg_invoice[2]:,.2f})')

    lms_conn.close()
    pg_conn.close()

    print('\n\n' + '=' * 100)
    print('CONCLUSION')
    print('=' * 100)
    print('\nLMS stores ONLY the base rate - no separate gratuity or charges.')
    print('PostgreSQL adds charter_charges table with GST, fuel, gratuity, etc.')
    print('')
    print('This explains the 61.3% payment rate:')
    print('  - Deposits were recorded based on LMS Rate amounts')
    print('  - But PostgreSQL total_invoice includes Rate + Gratuity + Charges')
    print('  - So deposits appear SHORT when compared to inflated invoice totals')
    print('')
    print('QUESTION: Are charter_charges REAL invoiced amounts, or internal tracking?')

if __name__ == '__main__':
    main()
