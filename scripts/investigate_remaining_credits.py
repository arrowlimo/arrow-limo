#!/usr/bin/env python
"""
Investigate the 9 remaining urgent credit charters.
"""
import psycopg2
import pyodbc

reserves = ['019536', '017328', '019571', '014089', '019657', '003708', '019586', '014147', '010999']

pg_conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
pg_cur = pg_conn.cursor()

LMS_PATH = r'L:\limo\backups\lms.mdb'
lms_conn = pyodbc.connect(f'DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={LMS_PATH};')
lms_cur = lms_conn.cursor()

print('='*100)
print('INVESTIGATING 9 REMAINING URGENT CREDITS')
print('='*100)

for reserve in reserves:
    print(f'\n{"="*100}')
    print(f'CHARTER {reserve}')
    print(f'{"="*100}')
    
    # PostgreSQL data
    pg_cur.execute("""
        SELECT reserve_number, total_amount_due, paid_amount, balance, 
               status, cancelled, notes
        FROM charters WHERE reserve_number = %s
    """, (reserve,))
    pg_row = pg_cur.fetchone()
    
    if pg_row:
        print(f'\nPostgreSQL Charter:')
        print(f'  total_amount_due: ${pg_row[1] or 0}')
        print(f'  paid_amount: ${pg_row[2] or 0}')
        print(f'  balance: ${pg_row[3] or 0}')
        print(f'  status: {pg_row[4]}')
        print(f'  cancelled: {pg_row[5]}')
        print(f'  notes: {pg_row[6][:100] if pg_row[6] else None}...')
    
    # PostgreSQL charges
    pg_cur.execute("""
        SELECT COUNT(*), SUM(amount)
        FROM charter_charges
        WHERE reserve_number = %s
    """, (reserve,))
    charges_count, charges_sum = pg_cur.fetchone()
    print(f'\nPostgreSQL Charges: {charges_count} rows, ${charges_sum or 0} total')
    
    # PostgreSQL payments via reserve_number in payments table
    pg_cur.execute("""
        SELECT payment_id, amount, payment_date, payment_method
        FROM payments
        WHERE reserve_number = %s
    """, (reserve,))
    payments = pg_cur.fetchall()
    print(f'\nPostgreSQL Payments (via reserve_number): {len(payments)} payments')
    for pmt in payments:
        print(f'  payment_id={pmt[0]}: ${pmt[1]} on {pmt[2]} via {pmt[3]}')
    
    # LMS data
    lms_cur.execute("""
        SELECT Rate, Est_Charge, Deposit, Balance, Status
        FROM Reserve
        WHERE Reserve_No = ?
    """, (reserve,))
    lms_row = lms_cur.fetchone()
    
    if lms_row:
        print(f'\nLMS Reserve:')
        print(f'  Rate: ${lms_row[0]}')
        print(f'  Est_Charge: ${lms_row[1] or 0}')
        print(f'  Deposit: ${lms_row[2] or 0}')
        print(f'  Balance: ${lms_row[3] or 0}')
        print(f'  Status: {lms_row[4]}')
    
    # LMS payments
    lms_cur.execute("""
        SELECT Amount, LastUpdated
        FROM Payment
        WHERE Reserve_No = ?
    """, (reserve,))
    lms_payments = lms_cur.fetchall()
    print(f'\nLMS Payments: {len(lms_payments)} payments, ${sum(p[0] or 0 for p in lms_payments)} total')
    for pmt in lms_payments[:5]:
        print(f'  ${pmt[0]} on {pmt[1]}')

pg_cur.close()
pg_conn.close()
lms_cur.close()
lms_conn.close()
print('\nDone.')
