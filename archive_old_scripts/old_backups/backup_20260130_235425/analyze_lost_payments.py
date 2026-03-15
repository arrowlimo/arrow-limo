#!/usr/bin/env python3
"""
Analyze the specific lost payments to understand the irregularities better.
"""

import pyodbc

OLD_LMS_PATH = r'L:\limo\backups\oldlms.mdb'
CURRENT_LMS_PATH = r'L:\limo\backups\lms.mdb'

def get_lms_connection(path):
    conn_str = f'DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={path};'
    return pyodbc.connect(conn_str)

def main():
    print('=' * 100)
    print('DETAILED ANALYSIS OF 6 LOST PAYMENTS')
    print('=' * 100)
    
    old_conn = get_lms_connection(OLD_LMS_PATH)
    curr_conn = get_lms_connection(CURRENT_LMS_PATH)
    
    lost_payment_ids = [23531, 23532, 23533, 23534, 23535, 24480]
    
    print('\nLOST PAYMENTS DETAILS (from OLD LMS):')
    print('-' * 100)
    
    old_cur = old_conn.cursor()
    for payment_id in lost_payment_ids:
        old_cur.execute("""
            SELECT 
                PaymentID,
                Reserve_No,
                Account_No,
                Amount,
                [Key],
                LastUpdated,
                LastUpdatedBy
            FROM Payment
            WHERE PaymentID = ?
        """, (payment_id,))
        
        row = old_cur.fetchone()
        if row:
            print(f'\nPayment ID: {row[0]}')
            print(f'  Reserve: {row[1]}')
            print(f'  Account: {row[2]}')
            print(f'  Amount: ${row[3]:.2f}')
            print(f'  Key: {row[4]}')
            print(f'  Last Updated: {row[5]}')
            print(f'  Updated By: {row[6]}')
            
            # Check if reserve exists in current
            reserve_no = row[1]
            if reserve_no:
                curr_cur = curr_conn.cursor()
                curr_cur.execute("SELECT Reserve_No, Name, PU_Date, Rate FROM Reserve WHERE Reserve_No = ?", (reserve_no,))
                reserve = curr_cur.fetchone()
                if reserve:
                    print(f'  → Reserve EXISTS in CURRENT: {reserve[1]}, Date: {reserve[2]}, Rate: ${reserve[3]:.2f}')
                    
                    # Check if reserve has any payments in current
                    curr_cur.execute("SELECT COUNT(*), SUM(Amount) FROM Payment WHERE Reserve_No = ?", (reserve_no,))
                    curr_payments = curr_cur.fetchone()
                    total = curr_payments[1] if curr_payments[1] else 0
                    print(f'  → CURRENT has {curr_payments[0]} payment(s) totaling ${total:.2f}')
                else:
                    print(f'  → Reserve DOES NOT EXIST in CURRENT')
    
    # Check the payment key pattern
    print('\n\n' + '=' * 100)
    print('PAYMENT KEY ANALYSIS')
    print('=' * 100)
    
    # Key 0021138 appears 5 times
    print('\nKey 0021138 (5 lost payments):')
    old_cur.execute("""
        SELECT PaymentID, Reserve_No, Amount, LastUpdated
        FROM Payment
        WHERE [Key] = '0021138'
        ORDER BY PaymentID
    """)
    
    for row in old_cur.fetchall():
        print(f'  Payment {row[0]}: Reserve {row[1]}, ${row[2]:.2f}, Date: {row[3]}')
    
    # Check if this key exists in current
    curr_cur = curr_conn.cursor()
    curr_cur.execute("SELECT COUNT(*) FROM Payment WHERE [Key] = '0021138'")
    curr_count = curr_cur.fetchone()[0]
    print(f'\n  → Key 0021138 appears {curr_count} times in CURRENT LMS')
    
    # Key 0021917
    print('\nKey 0021917 (1 lost payment):')
    old_cur.execute("""
        SELECT PaymentID, Reserve_No, Amount, LastUpdated
        FROM Payment
        WHERE [Key] = '0021917'
        ORDER BY PaymentID
    """)
    
    for row in old_cur.fetchall():
        print(f'  Payment {row[0]}: Reserve {row[1]}, ${row[2]:.2f}, Date: {row[3]}')
    
    curr_cur.execute("SELECT COUNT(*) FROM Payment WHERE [Key] = '0021917'")
    curr_count = curr_cur.fetchone()[0]
    print(f'\n  → Key 0021917 appears {curr_count} times in CURRENT LMS')
    
    # Check if these payment IDs are just renumbered
    print('\n\n' + '=' * 100)
    print('PAYMENT ID RANGE ANALYSIS')
    print('=' * 100)
    
    old_cur.execute("SELECT MIN(PaymentID), MAX(PaymentID) FROM Payment")
    old_range = old_cur.fetchone()
    print(f'\nOLD LMS Payment ID range: {old_range[0]} to {old_range[1]}')
    
    curr_cur.execute("SELECT MIN(PaymentID), MAX(PaymentID) FROM Payment")
    curr_range = curr_cur.fetchone()
    print(f'CURRENT LMS Payment ID range: {curr_range[0]} to {curr_range[1]}')
    
    print('\n⚠ Lost payment IDs are in the middle of the range!')
    print('  These are NOT just new payments with higher IDs.')
    print('  Payment IDs 23531-23535 and 24480 were removed/deleted.')
    
    old_conn.close()
    curr_conn.close()
    
    print('\n' + '=' * 100)
    print('ANALYSIS COMPLETE')
    print('=' * 100)

if __name__ == '__main__':
    main()
