import pyodbc
import psycopg2

# Connect to LMS
lms_conn_str = r'Driver={Microsoft Access Driver (*.mdb, *.accdb)};DBQ=L:\limo\backups\lms.mdb;'
lms_conn = pyodbc.connect(lms_conn_str)
lms_cur = lms_conn.cursor()

# Connect to ALMS
alms_conn = psycopg2.connect(host='localhost', dbname='almsdata', user='postgres', password='***REMOVED***')
alms_cur = alms_conn.cursor()

reserve_num = '019618'

print('='*80)
print(f'COMPLETE CHARTER AUDIT: {reserve_num}')
print('='*80)

# ========== LMS DATA ==========
print('\n📋 LMS (SOURCE OF TRUTH)\n')

# Reserve header
lms_cur.execute('SELECT Reserve_No, PU_Date, Driver, Status FROM Reserve WHERE Reserve_No = ?', (reserve_num,))
res_row = lms_cur.fetchone()
if res_row:
    print(f'Reserve: {res_row[0]} | Date: {res_row[1].date()} | Driver: {res_row[2]} | Status: {res_row[3]}')

# Charges
lms_cur.execute('SELECT Desc, Amount FROM Charge WHERE Reserve_No = ?', (reserve_num,))
charges = lms_cur.fetchall()
total_charges = 0
print(f'\nCharges:')
for desc, amt in charges:
    amt = amt or 0
    total_charges += amt
    print(f'  {desc:30} ${amt:>10,.2f}')
print(f'  {"TOTAL CHARGES":30} ${total_charges:>10,.2f}')

# Payments
lms_cur.execute('SELECT PaymentID, Amount FROM Payment WHERE Reserve_No = ?', (reserve_num,))
payments = lms_cur.fetchall()
total_paid_lms = 0
print(f'\nPayments:')
for pid, amt in payments:
    amt = amt or 0
    total_paid_lms += amt
    print(f'  PaymentID {pid:15} ${amt:>10,.2f}')
print(f'  {"TOTAL PAID (LMS)":30} ${total_paid_lms:>10,.2f}')

# Balance
lms_balance = total_charges - total_paid_lms
print(f'  {"BALANCE OWING (LMS)":30} ${lms_balance:>10,.2f}')

# ========== ALMS DATA ==========
print('\n' + '='*80)
print('\n📊 ALMS (NEW SYSTEM)\n')

alms_cur.execute('''
    SELECT reserve_number, charter_date, total_amount_due, status
    FROM charters
    WHERE reserve_number = %s
''', (reserve_num,))
alms_charter = alms_cur.fetchone()
if alms_charter:
    charter_date = alms_charter[1]
    if hasattr(charter_date, 'date'):
        charter_date = charter_date.date()
    print(f'Charter: {alms_charter[0]} | Date: {charter_date} | Status: {alms_charter[3]}')
    print(f'\nCharges (ALMS total_amount_due): ${alms_charter[2]:,.2f}')
    
    # Payments in ALMS
    alms_cur.execute('''
        SELECT SUM(amount) FROM payments
        WHERE reserve_number = %s AND amount > 0
    ''', (reserve_num,))
    total_paid_alms = alms_cur.fetchone()[0] or 0
    print(f'Total Paid (ALMS):               ${total_paid_alms:,.2f}')
    
    alms_balance = alms_charter[2] - total_paid_alms
    print(f'Balance Owing (ALMS):            ${alms_balance:,.2f}')
else:
    print('❌ Charter not found in ALMS!')

# ========== COMPARISON ==========
print('\n' + '='*80)
print('\n🔍 COMPARISON\n')
print(f'Charges:     LMS: ${total_charges:>10,.2f} | ALMS: ${alms_charter[2]:>10,.2f} | Match: {"✅" if total_charges == alms_charter[2] else "❌"}')
print(f'Paid:        LMS: ${total_paid_lms:>10,.2f} | ALMS: ${total_paid_alms:>10,.2f} | Match: {"✅" if total_paid_lms == total_paid_alms else "❌"}')
print(f'Balance:     LMS: ${lms_balance:>10,.2f} | ALMS: ${alms_balance:>10,.2f} | Match: {"✅" if lms_balance == alms_balance else "❌"}')

lms_cur.close()
lms_conn.close()
alms_cur.close()
alms_conn.close()
