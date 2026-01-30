#!/usr/bin/env python
"""
For urgent credits that show $0 in LMS, check if PostgreSQL charges match LMS rates.
Hypothesis: PostgreSQL has incorrect total_amount_due compared to LMS.
"""
import psycopg2
import pyodbc

# Sample urgent credits that LMS shows as $0 balance
SAMPLE_CHARTERS = ['009854', '017328', '010073', '019536', '019571', 
                   '017429', '009973', '014089', '007346', '008866']

# Connect to databases
pg_conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
pg_cur = pg_conn.cursor()

LMS_PATH = r'L:\limo\backups\lms.mdb'
lms_conn_str = f'DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={LMS_PATH};'
lms_conn = pyodbc.connect(lms_conn_str)
lms_cur = lms_conn.cursor()

print('='*100)
print('CHARGE COMPARISON: PostgreSQL vs LMS')
print('='*100)

for reserve_number in SAMPLE_CHARTERS:
    print(f'\n{reserve_number}:')
    
    # Get PostgreSQL data
    pg_cur.execute("""
        SELECT total_amount_due, paid_amount, balance,
               (SELECT SUM(amount) FROM charter_charges WHERE reserve_number = %s) as charge_sum,
               (SELECT SUM(amount) FROM charter_payments WHERE charter_id = %s) as payment_sum
        FROM charters WHERE reserve_number = %s
    """, (reserve_number, reserve_number, reserve_number))
    pg_row = pg_cur.fetchone()
    
    if pg_row:
        pg_total_due, pg_paid, pg_balance, pg_charge_sum, pg_payment_sum = pg_row
        print(f'  PG: total_due={pg_total_due} charges_sum={pg_charge_sum}')
        print(f'      paid_amount={pg_paid} payment_sum={pg_payment_sum}')
        print(f'      balance={pg_balance}')
        
    # Get LMS data
    lms_cur.execute("SELECT Rate, Balance, Deposit FROM Reserve WHERE Reserve_No = ?", (reserve_number,))
    lms_row = lms_cur.fetchone()
    
    if lms_row:
        lms_rate, lms_balance, lms_deposit = lms_row
        print(f'  LMS: rate={lms_rate} deposit={lms_deposit} balance={lms_balance}')
        
        # Compare
        if pg_total_due and abs(float(pg_total_due) - float(lms_rate)) > 1.0:
            print(f'  [FAIL] CHARGE MISMATCH: PG total_due={pg_total_due} vs LMS rate={lms_rate}')
        
        if pg_paid and lms_deposit and abs(float(pg_paid) - float(lms_deposit)) > 1.0:
            print(f'  [FAIL] PAYMENT MISMATCH: PG paid={pg_paid} vs LMS deposit={lms_deposit}')

lms_cur.close()
lms_conn.close()
pg_cur.close()
pg_conn.close()

print('\nDone.')
