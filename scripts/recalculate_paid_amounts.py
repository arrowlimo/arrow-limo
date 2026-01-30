#!/usr/bin/env python
"""
Recalculate paid_amount for charters based on ACTUAL charter_payments linkages.
Compare with LMS to verify correctness.

Pattern found: Many charters have inflated paid_amount that doesn't match 
the sum of charter_payments.amount for that charter.
"""
import psycopg2
import pyodbc
import argparse

parser = argparse.ArgumentParser(description='Recalculate charter paid_amounts from charter_payments linkages.')
parser.add_argument('--write', action='store_true', help='Apply corrections; default is dry-run.')
parser.add_argument('--verify-lms', action='store_true', help='Verify against LMS after recalculation.')
args = parser.parse_args()

# Connect to PostgreSQL
pg_conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
pg_cur = pg_conn.cursor()

print('='*100)
print('Recalculate Charter paid_amount from charter_payments Linkages')
print('='*100)

# Find charters where paid_amount != SUM(charter_payments.amount)
pg_cur.execute("""
    WITH cp_sum AS (
        SELECT charter_id, COALESCE(SUM(amount), 0) as total_cp_amount
        FROM charter_payments
        GROUP BY charter_id
    )
    SELECT c.reserve_number,
           c.paid_amount as current_paid,
           COALESCE(cp.total_cp_amount, 0) as calculated_paid,
           c.total_amount_due,
           c.balance as current_balance
    FROM charters c
    LEFT JOIN cp_sum cp ON cp.charter_id = c.reserve_number
    WHERE ABS(COALESCE(c.paid_amount, 0) - COALESCE(cp.total_cp_amount, 0)) > 0.01
    ORDER BY (COALESCE(c.paid_amount, 0) - COALESCE(cp.total_cp_amount, 0)) ASC
    LIMIT 1000
""")
discrepancies = pg_cur.fetchall()

print(f'\nFound {len(discrepancies)} charters with paid_amount != SUM(charter_payments)')

# Show top 20 largest discrepancies
print('\nTop 20 largest discrepancies:')
for r in discrepancies[:20]:
    reserve_number, current_paid, calculated_paid, total_due, current_balance = r
    diff = (current_paid or 0) - (calculated_paid or 0)
    print(f'  {reserve_number}: current_paid=${current_paid} calculated=${calculated_paid} diff=${diff:,.2f}')

total_adjustment = sum((r[1] or 0) - (r[2] or 0) for r in discrepancies)
print(f'\nTotal paid_amount adjustment needed: ${total_adjustment:,.2f}')

if not args.write:
    print('\nDRY RUN - no changes made. Use --write to apply corrections.')
    pg_cur.close()
    pg_conn.close()
    exit(0)

# Apply corrections
print('\nApplying corrections...')
corrected_count = 0
for r in discrepancies:
    reserve_number, current_paid, calculated_paid, total_due, current_balance = r
    
    # Recalculate balance
    new_balance = (total_due or 0) - calculated_paid
    
    pg_cur.execute("""
        UPDATE charters
        SET paid_amount = %s,
            balance = %s,
            updated_at = CURRENT_TIMESTAMP
        WHERE reserve_number = %s
    """, (calculated_paid, new_balance, reserve_number))
    
    corrected_count += 1
    if corrected_count % 100 == 0:
        print(f'  Corrected {corrected_count}/{len(discrepancies)}...')

pg_conn.commit()
print(f'\n✓ Corrected {corrected_count} charters')
print(f'✓ Adjusted paid_amount by ${total_adjustment:,.2f}')

# Verify against LMS if requested
if args.verify_lms:
    print('\nVerifying urgent credits against LMS...')
    
    LMS_PATH = r'L:\limo\backups\lms.mdb'
    lms_conn_str = f'DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={LMS_PATH};'
    try:
        lms_conn = pyodbc.connect(lms_conn_str)
        lms_cur = lms_conn.cursor()
        
        # Check urgent credits again
        pg_cur.execute("""
            SELECT reserve_number, balance
            FROM charters
            WHERE balance < -2000
            LIMIT 10
        """)
        urgent_credits = pg_cur.fetchall()
        
        print(f'\nChecking {len(urgent_credits)} urgent credits:')
        for pg_row in urgent_credits:
            reserve_number, pg_balance = pg_row
            
            lms_cur.execute("SELECT Balance FROM Reserve WHERE Reserve_No = ?", (reserve_number,))
            lms_row = lms_cur.fetchone()
            
            if lms_row:
                lms_balance = float(lms_row[0]) if lms_row[0] else 0
                match = '✓' if abs(pg_balance - lms_balance) < 1.0 else '[FAIL]'
                print(f'  {match} {reserve_number}: PG=${pg_balance:,.2f} LMS=${lms_balance:,.2f}')
            else:
                print(f'  ⚠ {reserve_number}: NOT FOUND in LMS')
        
        lms_cur.close()
        lms_conn.close()
    except Exception as e:
        print(f'Could not verify against LMS: {e}')

pg_cur.close()
pg_conn.close()
print('\nDone.')
