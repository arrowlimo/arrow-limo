import pyodbc
import psycopg2

# Connect to LMS
lms_conn_str = r'Driver={Microsoft Access Driver (*.mdb, *.accdb)};DBQ=L:\limo\backups\lms.mdb;'
lms_conn = pyodbc.connect(lms_conn_str)
lms_cur = lms_conn.cursor()

# Connect to ALMS
alms_conn = psycopg2.connect(host='localhost', dbname='almsdata', user='postgres', password='***REDACTED***')
alms_cur = alms_conn.cursor()

print('=== CHARTER MATCHING AUDIT (20 SAMPLES) ===\n')

# Get 20 random charters from ALMS that have employee_id set (active charters)
alms_cur.execute('''
    SELECT reserve_number, total_amount_due
    FROM charters
    WHERE employee_id IS NOT NULL
    AND status NOT IN ('cancelled', 'Cancelled', 'CANCELLED', '')
    ORDER BY RANDOM()
    LIMIT 20
''')

samples = alms_cur.fetchall()
matches = 0
mismatches = []

for reserve_num, alms_charges in samples:
    alms_charges = float(alms_charges or 0)
    # Get LMS totals
    lms_cur.execute('SELECT SUM(Amount) FROM Charge WHERE Reserve_No = ?', (reserve_num,))
    lms_charges_row = lms_cur.fetchone()
    lms_charges_total = float(lms_charges_row[0] or 0)
    
    lms_cur.execute('SELECT SUM(Amount) FROM Payment WHERE Reserve_No = ?', (reserve_num,))
    lms_paid_row = lms_cur.fetchone()
    lms_paid_total = float(lms_paid_row[0] or 0)
    
    # Get ALMS totals
    alms_cur.execute('''
        SELECT SUM(amount) FROM payments
        WHERE reserve_number = %s AND amount > 0
    ''', (reserve_num,))
    alms_paid_row = alms_cur.fetchone()
    alms_paid_total = float(alms_paid_row[0] or 0)
    
    # Compare
    charges_match = abs(lms_charges_total - alms_charges) < 0.01
    paid_match = abs(lms_paid_total - alms_paid_total) < 0.01
    balance_match = charges_match and paid_match
    
    if balance_match:
        print(f'✅ {reserve_num} | Charges: ${lms_charges_total:>10,.2f} | Paid: ${lms_paid_total:>10,.2f}')
        matches += 1
    else:
        mismatch_details = []
        if not charges_match:
            mismatch_details.append(f'Charges: LMS ${lms_charges_total:,.2f} vs ALMS ${alms_charges:,.2f}')
        if not paid_match:
            mismatch_details.append(f'Paid: LMS ${lms_paid_total:,.2f} vs ALMS ${alms_paid_total:,.2f}')
        
        print(f'❌ {reserve_num} | {" | ".join(mismatch_details)}')
        mismatches.append(reserve_num)

print(f'\n✅ Matched: {matches}/20')
print(f'❌ Mismatched: {len(mismatches)}/20')

if mismatches:
    print(f'\nMismatched reserves: {mismatches}')

lms_cur.close()
lms_conn.close()
alms_cur.close()
alms_conn.close()
