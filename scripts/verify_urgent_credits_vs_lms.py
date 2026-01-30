#!/usr/bin/env python
"""
Check urgent credits against LMS to verify accuracy.
For each credit >$2K in our DB, check LMS for actual balance.
"""
import psycopg2
import pyodbc

# Connect to PostgreSQL
pg_conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
pg_cur = pg_conn.cursor()

# Connect to LMS
LMS_PATH = r'L:\limo\backups\lms.mdb'
lms_conn_str = f'DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={LMS_PATH};'
try:
    lms_conn = pyodbc.connect(lms_conn_str)
    lms_cur = lms_conn.cursor()
except Exception as e:
    print(f'ERROR: Cannot connect to LMS database: {e}')
    print(f'Path: {LMS_PATH}')
    pg_cur.close()
    pg_conn.close()
    exit(1)

print('='*100)
print('URGENT CREDITS VERIFICATION vs LMS')
print('='*100)

# Get urgent credits from PostgreSQL
pg_cur.execute("""
    SELECT reserve_number, charter_date, total_amount_due, paid_amount, balance
    FROM charters
    WHERE balance < -2000
    ORDER BY balance ASC
    LIMIT 35
""")
pg_credits = pg_cur.fetchall()

print(f'\nPostgreSQL: {len(pg_credits)} charters with credits > $2,000')

# Check each in LMS
mismatches = []
for pg_row in pg_credits:
    reserve_number, charter_date, total_due, paid, balance = pg_row
    
    # Look up in LMS
    lms_cur.execute("""
        SELECT Reserve_No, Rate, Balance, Deposit
        FROM Reserve
        WHERE Reserve_No = ?
    """, (reserve_number,))
    lms_row = lms_cur.fetchone()
    
    if lms_row:
        lms_reserve, lms_rate, lms_balance, lms_deposit = lms_row
        
        # Compare
        pg_balance = float(balance) if balance else 0
        lms_bal = float(lms_balance) if lms_balance else 0
        
        diff = abs(pg_balance - lms_bal)
        
        if diff > 1.0:  # More than $1 difference
            mismatches.append({
                'reserve': reserve_number,
                'pg_balance': pg_balance,
                'lms_balance': lms_bal,
                'difference': pg_balance - lms_bal,
                'pg_paid': paid,
                'pg_total_due': total_due,
                'lms_rate': lms_rate,
                'lms_deposit': lms_deposit
            })
            print(f'\n[FAIL] MISMATCH: {reserve_number}')
            print(f'   PG: total_due={total_due} paid={paid} balance={pg_balance}')
            print(f'   LMS: rate={lms_rate} deposit={lms_deposit} balance={lms_bal}')
            print(f'   DIFFERENCE: {pg_balance - lms_bal}')
        else:
            print(f'✓ {reserve_number}: PG={pg_balance} LMS={lms_bal}')
    else:
        print(f'⚠ {reserve_number}: NOT FOUND in LMS')
        mismatches.append({
            'reserve': reserve_number,
            'pg_balance': float(balance) if balance else 0,
            'lms_balance': None,
            'difference': None,
            'pg_paid': paid,
            'pg_total_due': total_due,
            'lms_rate': None,
            'lms_deposit': None
        })

print(f'\n{'='*100}')
print(f'SUMMARY: {len(mismatches)} mismatches out of {len(pg_credits)} checked')
print(f'{'='*100}')

if mismatches:
    print('\nMISMATCHES DETAIL:')
    for m in mismatches[:20]:  # Show first 20
        print(f"\n{m['reserve']}:")
        print(f"  PostgreSQL balance: ${m['pg_balance']:,.2f}")
        print(f"  LMS balance: ${m['lms_balance']:,.2f}" if m['lms_balance'] is not None else "  LMS: NOT FOUND")
        if m['difference'] is not None:
            print(f"  Difference: ${m['difference']:,.2f}")

lms_cur.close()
lms_conn.close()
pg_cur.close()
pg_conn.close()

print('\nDone.')
