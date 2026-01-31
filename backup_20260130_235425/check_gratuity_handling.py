#!/usr/bin/env python3
"""
Check how gratuity is handled in charter totals
Verify if gratuity should be added to invoice amounts
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
    print('GRATUITY/TIP HANDLING ANALYSIS')
    print('=' * 80)

    # Check for gratuity columns in charters table
    cur.execute("""
        SELECT column_name, data_type
        FROM information_schema.columns 
        WHERE table_name = 'charters' 
        AND column_name LIKE '%gratuity%'
        ORDER BY column_name
    """)
    
    gratuity_cols = cur.fetchall()
    print('\nGRATUITY COLUMNS IN CHARTERS TABLE:')
    for col in gratuity_cols:
        print(f'  {col[0]:40} {col[1]}')

    # Check gratuity statistics
    cur.execute("""
        SELECT 
            COUNT(*) as total_charters,
            SUM(CASE WHEN driver_gratuity > 0 THEN 1 ELSE 0 END) as with_gratuity,
            SUM(CASE WHEN driver_gratuity IS NULL THEN 1 ELSE 0 END) as null_gratuity,
            AVG(driver_gratuity) as avg_gratuity,
            SUM(driver_gratuity) as total_gratuity
        FROM charters
        WHERE cancelled = false
    """)
    
    stats = cur.fetchone()
    print('\n\nGRATUITY STATISTICS (charters table):')
    print('-' * 80)
    print(f'Total Charters: {stats[0]}')
    print(f'With Gratuity > 0: {stats[1]} ({stats[1]/stats[0]*100:.1f}%)')
    print(f'NULL Gratuity: {stats[2]} ({stats[2]/stats[0]*100:.1f}%)')
    print(f'Average Gratuity: ${stats[3]:.2f}' if stats[3] else 'N/A')
    print(f'Total Gratuity: ${stats[4]:.2f}' if stats[4] else 'N/A')

    # Sample charters with gratuity
    cur.execute("""
        SELECT 
            c.reserve_number,
            c.charter_date,
            c.rate,
            c.driver_gratuity,
            c.deposit,
            c.balance,
            COALESCE(
                (SELECT SUM(amount) 
                 FROM charter_charges cc 
                 WHERE cc.charter_id = c.charter_id 
                 AND cc.charge_type != 'customer_tip'),
                0
            ) as billable_charges,
            COALESCE(
                (SELECT SUM(amount) 
                 FROM charter_charges cc 
                 WHERE cc.charter_id = c.charter_id 
                 AND cc.charge_type = 'customer_tip'),
                0
            ) as customer_tips
        FROM charters c
        WHERE c.driver_gratuity > 0
        AND c.rate > 0
        ORDER BY c.charter_date DESC
        LIMIT 10
    """)
    
    samples = cur.fetchall()
    print('\n\nSAMPLE CHARTERS WITH DRIVER GRATUITY:')
    print('-' * 80)
    for s in samples:
        reserve = s[0]
        date = s[1]
        rate = s[2]
        gratuity = s[3]
        deposit = s[4] if s[4] else 0
        balance = s[5] if s[5] else 0
        charges = s[6]
        tips = s[7]
        
        total_invoice = rate + charges + gratuity
        
        print(f'\n{reserve} ({date}):')
        print(f'  Rate: ${rate:.2f}')
        print(f'  Billable Charges: ${charges:.2f}')
        print(f'  Driver Gratuity: ${gratuity:.2f}')
        print(f'  Customer Tips (charter_charges): ${tips:.2f}')
        print(f'  TOTAL INVOICE: ${total_invoice:.2f}')
        print(f'  Deposit Paid: ${deposit:.2f}')
        print(f'  Balance: ${balance:.2f}')
        if abs(total_invoice - deposit - balance) < 0.01:
            print(f'  ✓ BALANCED: ${total_invoice:.2f} = ${deposit:.2f} (paid) + ${balance:.2f} (owing)')
        else:
            print(f'  ✗ MISMATCH: Invoice ${total_invoice:.2f} != Deposit ${deposit:.2f} + Balance ${balance:.2f}')

    # Check charter 006587 specifically
    print('\n\n' + '=' * 80)
    print('CHARTER 006587 (King Kent) - GRATUITY CHECK')
    print('=' * 80)
    
    cur.execute("""
        SELECT 
            c.reserve_number,
            c.charter_date,
            c.rate,
            c.driver_gratuity,
            c.driver_gratuity_percent,
            c.driver_gratuity_amount,
            c.deposit,
            c.balance,
            COALESCE(
                (SELECT SUM(amount) 
                 FROM charter_charges cc 
                 WHERE cc.charter_id = c.charter_id),
                0
            ) as total_charges,
            COALESCE(
                (SELECT SUM(amount) 
                 FROM charter_charges cc 
                 WHERE cc.charter_id = c.charter_id 
                 AND cc.charge_type != 'customer_tip'),
                0
            ) as billable_charges
        FROM charters c
        WHERE c.charter_id = 5549
    """)
    
    kent = cur.fetchone()
    if kent:
        print(f'\nReserve: {kent[0]}')
        print(f'Date: {kent[1]}')
        print(f'Rate: ${kent[2]:.2f}')
        print(f'Driver Gratuity: ${kent[3]:.2f}' if kent[3] else 'NULL')
        print(f'Driver Gratuity %: {kent[4]}' if kent[4] else 'NULL')
        print(f'Driver Gratuity Amount: ${kent[5]:.2f}' if kent[5] else 'NULL')
        print(f'Deposit: ${kent[6]:.2f}' if kent[6] else 'NULL')
        print(f'Balance: ${kent[7]:.2f}' if kent[7] else 'NULL')
        print(f'Total Charges: ${kent[8]:.2f}')
        print(f'Billable Charges (excl. tips): ${kent[9]:.2f}')
        
        # Calculate totals
        rate = kent[2] if kent[2] else 0
        gratuity = kent[3] if kent[3] else 0
        charges = kent[9]  # billable only
        
        print(f'\nCALCULATION:')
        print(f'  Rate: ${rate:.2f}')
        print(f'  + Billable Charges: ${charges:.2f}')
        print(f'  + Driver Gratuity: ${gratuity:.2f}')
        print(f'  = TOTAL: ${rate + charges + gratuity:.2f}')
        print(f'\nFrom LMS screenshot: $210 + $10.50 GST + $10.50 fuel = $231')
        print(f'Charter charges total: ${kent[8]:.2f} (includes $210 + $10.50 + $10.50)')

    cur.close()
    conn.close()

    print('\n\n' + '=' * 80)
    print('CONCLUSION')
    print('=' * 80)
    print('\nFor COMPLETE invoice totals:')
    print('  Total Amount = rate + billable_charges + driver_gratuity')
    print('')
    print('Where:')
    print('  - rate = base charter rate')
    print('  - billable_charges = SUM(charter_charges) WHERE charge_type != "customer_tip"')
    print('  - driver_gratuity = automatic gratuity added to invoice (if any)')
    print('  - customer_tip = additional tip paid by customer (already collected)')

if __name__ == '__main__':
    main()
