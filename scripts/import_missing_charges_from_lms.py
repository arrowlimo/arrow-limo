#!/usr/bin/env python
"""
Import charges from LMS for charters with 0 charges but payments recorded.
"""
import psycopg2
import pyodbc
import argparse

parser = argparse.ArgumentParser(description='Import charges from LMS for charters missing charges.')
parser.add_argument('--write', action='store_true', help='Apply imports; default is dry-run.')
args = parser.parse_args()

reserves = ['019536', '019571', '019657', '019586', '016771']

pg_conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
pg_cur = pg_conn.cursor()

LMS_PATH = r'L:\limo\backups\lms.mdb'
lms_conn = pyodbc.connect(f'DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={LMS_PATH};')
lms_cur = lms_conn.cursor()

print('='*100)
print('IMPORT CHARGES FROM LMS FOR CHARTERS WITH 0 CHARGES')
print('='*100)

for reserve in reserves:
    print(f'\n{"="*100}')
    print(f'CHARTER {reserve}')
    print(f'{"="*100}')
    
    # Get LMS Est_Charge (total with extras)
    lms_cur.execute("""
        SELECT Rate, Est_Charge, Deposit, Balance
        FROM Reserve
        WHERE Reserve_No = ?
    """, (reserve,))
    lms_row = lms_cur.fetchone()
    
    if not lms_row:
        print(f'  ✗ Not found in LMS')
        continue
    
    rate, est_charge, deposit, balance = lms_row
    print(f'  LMS: Rate=${rate}, Est_Charge=${est_charge or 0}, Deposit=${deposit or 0}, Balance=${balance or 0}')
    
    # Check current PG state
    pg_cur.execute("""
        SELECT total_amount_due, paid_amount, balance,
               (SELECT COUNT(*) FROM charter_charges WHERE reserve_number = %s)
        FROM charters WHERE reserve_number = %s
    """, (reserve, reserve))
    pg_row = pg_cur.fetchone()
    
    if pg_row:
        total_due, paid, bal, charge_count = pg_row
        print(f'  PG: total_due=${total_due or 0}, paid=${paid or 0}, balance=${bal or 0}, charges={charge_count}')
    
    if charge_count > 0:
        print(f'  ⚠ Already has {charge_count} charges - skipping')
        continue
    
    if not est_charge:
        print(f'  ⚠ LMS Est_Charge is NULL - skipping')
        continue
    
    print(f'  → Will create charge for ${est_charge} and set total_amount_due=${est_charge}')
    
    if args.write:
        # Insert charge
        pg_cur.execute("""
            INSERT INTO charter_charges (reserve_number, description, amount, created_at)
            VALUES (%s, %s, %s, CURRENT_TIMESTAMP)
        """, (reserve, f'Charter total (from LMS Est_Charge)', est_charge))
        
        # Update charter totals
        new_balance = est_charge - (paid or 0)
        pg_cur.execute("""
            UPDATE charters
            SET total_amount_due = %s,
                balance = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE reserve_number = %s
        """, (est_charge, new_balance, reserve))
        
        print(f'  ✓ Created charge ${est_charge}, new_balance=${new_balance}')

if args.write:
    pg_conn.commit()
    print('\n✓ All changes committed')
    
    # Check remaining urgent credits
    pg_cur.execute("SELECT COUNT(*), SUM(balance) FROM charters WHERE balance < -2000")
    urgent_count, urgent_total = pg_cur.fetchone()
    print(f'\nRemaining urgent credits (< -$2K): {urgent_count} charters, ${urgent_total or 0:,.2f}')
else:
    print('\nDRY RUN - no changes made. Use --write to import charges.')

pg_cur.close()
pg_conn.close()
lms_cur.close()
lms_conn.close()
print('\nDone.')
