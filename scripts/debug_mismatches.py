import pyodbc
import psycopg2

# Connect to LMS
lms_conn_str = r'Driver={Microsoft Access Driver (*.mdb, *.accdb)};DBQ=L:\limo\backups\lms.mdb;'
lms_conn = pyodbc.connect(lms_conn_str)
lms_cur = lms_conn.cursor()

# Connect to ALMS
alms_conn = psycopg2.connect(host='localhost', dbname='almsdata', user='postgres', password='***REDACTED***')
alms_cur = alms_conn.cursor()

problem_reserves = ['016624', '016617']

for reserve_num in problem_reserves:
    print(f'\n{"="*80}')
    print(f'PROBLEM CHARTER: {reserve_num}')
    print(f'{"="*80}\n')
    
    # LMS
    print('LMS Charges:')
    lms_cur.execute('SELECT [Desc], Amount FROM Charge WHERE Reserve_No = ?', (reserve_num,))
    lms_charges = []
    for desc, amt in lms_cur.fetchall():
        amt = float(amt or 0)
        lms_charges.append(amt)
        print(f'  {desc:30} ${amt:>10,.2f}')
    total_lms_charges = sum(lms_charges)
    print(f'  {"TOTAL":30} ${total_lms_charges:>10,.2f}')
    
    print('\nLMS Payments:')
    lms_cur.execute('SELECT PaymentID, Amount FROM Payment WHERE Reserve_No = ?', (reserve_num,))
    lms_payments = []
    for pid, amt in lms_cur.fetchall():
        amt = float(amt or 0)
        lms_payments.append(amt)
        print(f'  PaymentID {pid:15} ${amt:>10,.2f}')
    total_lms_paid = sum(lms_payments)
    print(f'  {"TOTAL":30} ${total_lms_paid:>10,.2f}')
    print(f'\nLMS Balance: ${total_lms_charges - total_lms_paid:,.2f}')
    
    # ALMS
    print('\n' + '-'*80)
    print('\nALMS Charges:')
    alms_cur.execute('SELECT total_amount_due FROM charters WHERE reserve_number = %s', (reserve_num,))
    alms_row = alms_cur.fetchone()
    alms_charges_total = float(alms_row[0] or 0) if alms_row else 0
    print(f'  total_amount_due: ${alms_charges_total:,.2f}')
    
    print('\nALMS Payments:')
    alms_cur.execute('''
        SELECT payment_id, amount, payment_date, reference_number, payment_method
        FROM payments
        WHERE reserve_number = %s
        ORDER BY payment_date
    ''', (reserve_num,))
    alms_paid_records = alms_cur.fetchall()
    alms_paid_total = 0
    for pid, amt, date, ref, method in alms_paid_records:
        amt = float(amt)
        alms_paid_total += amt
        ref = ref or 'NULL'
        method = method or 'NULL'
        print(f'  ID {pid:6} | ${amt:>10,.2f} | {date} | {method:15} | {ref}')
    print(f'  {"TOTAL":30} ${alms_paid_total:>10,.2f}')
    print(f'\nALMS Balance: ${alms_charges_total - alms_paid_total:,.2f}')
    
    print(f'\n⚠️ DISCREPANCY:')
    print(f'  Charges: LMS ${total_lms_charges:,.2f} vs ALMS ${alms_charges_total:,.2f} (diff: ${abs(total_lms_charges - alms_charges_total):,.2f})')
    print(f'  Paid:    LMS ${total_lms_paid:,.2f} vs ALMS ${alms_paid_total:,.2f} (diff: ${abs(total_lms_paid - alms_paid_total):,.2f})')

lms_cur.close()
lms_conn.close()
alms_cur.close()
alms_conn.close()
