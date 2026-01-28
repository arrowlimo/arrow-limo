#!/usr/bin/env python3
"""
Investigate AUDIT refund pair records - why they exist and what they represent
"""

import psycopg2
import pyodbc
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
    print('=' * 80)
    print('AUDIT REFUND PAIR INVESTIGATION')
    print('=' * 80)

    pg_conn = get_pg_connection()
    pg_cur = pg_conn.cursor()

    # Get both AUDIT records
    pg_cur.execute("""
        SELECT 
            charter_id,
            reserve_number,
            charter_date,
            rate,
            balance,
            deposit,
            notes,
            booking_notes,
            created_at
        FROM charters
        WHERE reserve_number LIKE 'AUDIT%'
        ORDER BY reserve_number
    """)
    
    audit_records = pg_cur.fetchall()
    
    print('\nAUDIT RECORDS IN POSTGRESQL:')
    print('-' * 80)
    for ar in audit_records:
        print(f'\nCharter ID: {ar[0]}')
        print(f'Reserve Number: {ar[1]}')
        print(f'Charter Date: {ar[2]}')
        print(f'Rate: ${ar[3]:.2f}' if ar[3] else 'NULL')
        print(f'Balance: ${ar[4]:.2f}' if ar[4] else 'NULL')
        print(f'Deposit: ${ar[5]:.2f}' if ar[5] else 'NULL')
        print(f'Notes: {ar[6]}')
        print(f'Booking Notes: {ar[7]}')
        print(f'Created At: {ar[8]}')

    # Check if these exist in LMS
    print('\n\n' + '=' * 80)
    print('CHECKING LMS FOR THESE RESERVE NUMBERS')
    print('=' * 80)
    
    lms_conn = get_lms_connection()
    lms_cur = lms_conn.cursor()
    
    for ar in audit_records:
        reserve_num = ar[1]
        
        # Strip AUDIT prefix for LMS lookup
        if reserve_num.startswith('AUDIT'):
            numeric_part = reserve_num.replace('AUDIT', '')
            
            print(f'\n\nSearching LMS for Reserve_No = {numeric_part}:')
            print('-' * 80)
            
            try:
                lms_cur.execute("""
                    SELECT 
                        Reserve_No,
                        Account_No,
                        PU_Date,
                        Rate,
                        Balance,
                        Deposit,
                        Name,
                        Notes
                    FROM Reserve
                    WHERE Reserve_No = ?
                """, (numeric_part,))
                
                lms_record = lms_cur.fetchone()
                if lms_record:
                    print(f'✓ FOUND in LMS:')
                    print(f'  Reserve_No: {lms_record[0]}')
                    print(f'  Account_No: {lms_record[1]}')
                    print(f'  PU_Date: {lms_record[2]}')
                    print(f'  Rate: ${lms_record[3]:.2f}' if lms_record[3] else 'NULL')
                    print(f'  Balance: ${lms_record[4]:.2f}' if lms_record[4] else 'NULL')
                    print(f'  Deposit: ${lms_record[5]:.2f}' if lms_record[5] else 'NULL')
                    print(f'  Name: {lms_record[6]}')
                    print(f'  Notes: {lms_record[7]}')
                    
                    # Check for payments
                    lms_cur.execute("""
                        SELECT 
                            PaymentID,
                            Amount,
                            LastUpdated,
                            [Key]
                        FROM Payment
                        WHERE Reserve_No = ?
                        ORDER BY LastUpdated
                    """, (numeric_part,))
                    
                    payments = lms_cur.fetchall()
                    if payments:
                        print(f'\n  Payments:')
                        for p in payments:
                            print(f'    Payment {p[0]}: ${p[1]:.2f} on {p[2]} (Key: {p[3]})')
                    else:
                        print(f'\n  No payments found')
                else:
                    print(f'✗ NOT FOUND in LMS')
            except Exception as e:
                print(f'Error: {e}')

    # Look for the pair reference - 3634
    print('\n\n' + '=' * 80)
    print('LOOKING FOR RESERVE 003634 (THE PAIR)')
    print('=' * 80)
    
    lms_cur.execute("""
        SELECT 
            Reserve_No,
            Account_No,
            PU_Date,
            Rate,
            Balance,
            Deposit,
            Name,
            Notes
        FROM Reserve
        WHERE Reserve_No = '003634'
    """)
    
    pair_record = lms_cur.fetchone()
    if pair_record:
        print(f'\n✓ FOUND Reserve 003634 in LMS:')
        print(f'  Account_No: {pair_record[1]}')
        print(f'  PU_Date: {pair_record[2]}')
        print(f'  Rate: ${pair_record[3]:.2f}' if pair_record[3] else 'NULL')
        print(f'  Balance: ${pair_record[4]:.2f}' if pair_record[4] else 'NULL')
        print(f'  Deposit: ${pair_record[5]:.2f}' if pair_record[5] else 'NULL')
        print(f'  Name: {pair_record[6]}')
        print(f'  Notes: {pair_record[7]}')
        
        # Check payments for 003634
        lms_cur.execute("""
            SELECT 
                PaymentID,
                Amount,
                LastUpdated,
                [Key]
            FROM Payment
            WHERE Reserve_No = '003634'
            ORDER BY LastUpdated
        """)
        
        pair_payments = lms_cur.fetchall()
        if pair_payments:
            print(f'\n  Payments:')
            for p in pair_payments:
                print(f'    Payment {p[0]}: ${p[1]:.2f} on {p[2]} (Key: {p[3]})')
    else:
        print(f'\n✗ Reserve 003634 NOT FOUND in LMS')
    
    # Check PostgreSQL for 003634
    pg_cur.execute("""
        SELECT 
            charter_id,
            reserve_number,
            charter_date,
            rate,
            balance,
            deposit,
            notes,
            booking_notes
        FROM charters
        WHERE reserve_number = '003634'
    """)
    
    pg_pair = pg_cur.fetchone()
    if pg_pair:
        print(f'\n\n✓ FOUND Reserve 003634 in PostgreSQL:')
        print(f'  Charter ID: {pg_pair[0]}')
        print(f'  Reserve Number: {pg_pair[1]}')
        print(f'  Charter Date: {pg_pair[2]}')
        print(f'  Rate: ${pg_pair[3]:.2f}' if pg_pair[3] else 'NULL')
        print(f'  Balance: ${pg_pair[4]:.2f}' if pg_pair[4] else 'NULL')
        print(f'  Deposit: ${pg_pair[5]:.2f}' if pg_pair[5] else 'NULL')
        print(f'  Notes: {pg_pair[6]}')
        print(f'  Booking Notes: {pg_pair[7]}')
    else:
        print(f'\n✗ Reserve 003634 NOT FOUND in PostgreSQL')

    lms_conn.close()
    pg_conn.close()

    print('\n\n' + '=' * 80)
    print('ANALYSIS: WHAT ARE REFUND PAIRS?')
    print('=' * 80)
    print("""
REFUND PAIR = Two offsetting accounting entries to record a refund/reversal

Example scenario:
1. Customer books charter 003634 for $684, pays deposit
2. Later, charter is cancelled and customer gets refund
3. To maintain audit trail, system creates TWO entries:
   - AUDIT003634: Records the refund/reversal ($684 credit)
   - Original 003634: Keeps original booking ($684 debit)
   - Net effect: $0 (refund cancels original charge)

Why "AUDIT" prefix?
- Marks as internal accounting entry (not a real charter)
- Prevents double-counting in revenue reports
- Maintains audit trail for CRA compliance

Why not just delete the original?
- Accounting best practice: never delete, always adjust
- Audit trail requirement for tax purposes
- Shows complete transaction history

RECOMMENDATION:
- Exclude AUDIT* records from operational reports
- Include in financial audit reports to show full transaction history
- Net effect of refund pairs should always be $0
    """)

if __name__ == '__main__':
    main()
