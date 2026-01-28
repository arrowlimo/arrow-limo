import pyodbc
import psycopg2

# Connect to LMS (source of truth)
lms_conn_str = r'Driver={Microsoft Access Driver (*.mdb, *.accdb)};DBQ=L:\limo\backups\lms.mdb;'
lms_conn = pyodbc.connect(lms_conn_str)
lms_cur = lms_conn.cursor()

# Connect to ALMS (destination - needs cleanup)
alms_conn = psycopg2.connect(host='localhost', dbname='almsdata', user='postgres', password='***REMOVED***')
alms_cur = alms_conn.cursor()

print('=== ALMS PAYMENT CLEANUP AUDIT ===\n')
print('Comparing ALMS payments to LMS payments (source of truth)\n')

# Get all LMS payments with their reserve_number and PaymentID
lms_cur.execute('SELECT Reserve_No, PaymentID, Amount FROM Payment WHERE Reserve_No IS NOT NULL')
lms_payments = {}
for reserve_no, payment_id, amount in lms_cur.fetchall():
    reserve_no = str(reserve_no).strip()
    key = (reserve_no, int(payment_id))
    lms_payments[key] = float(amount or 0)

print(f'LMS has {len(lms_payments)} payment records\n')

# Now check ALMS payments
print('=== ALMS PAYMENTS TO DELETE ===\n')

# 1. All orphan payments (NULL reserve_number)
alms_cur.execute('SELECT COUNT(*), SUM(amount) FROM payments WHERE reserve_number IS NULL')
orphan_count, orphan_total = alms_cur.fetchone()
orphan_total = float(orphan_total or 0)
if orphan_count > 0:
    print(f'❌ {orphan_count} ORPHAN PAYMENTS (NULL reserve) | Total: ${orphan_total:,.2f}')
    alms_cur.execute('''
        SELECT payment_id, amount, payment_date
        FROM payments WHERE reserve_number IS NULL
        ORDER BY amount DESC LIMIT 5
    ''')
    for pid, amt, date in alms_cur.fetchall():
        print(f'     ID {pid} | ${float(amt):,.2f} | {date}')

# 2. Payments with amount mismatches (ALMS != LMS)
print(f'\n❌ AMOUNT MISMATCHES (ALMS != LMS):\n')
alms_cur.execute('''
    SELECT reserve_number, payment_id, amount
    FROM payments
    WHERE reserve_number IS NOT NULL
    AND amount > 0
    ORDER BY reserve_number
''')

mismatches = []
for reserve_no, alms_payment_id, alms_amount in alms_cur.fetchall():
    alms_amount = float(alms_amount)
    
    # Look for matching LMS payment
    key = (reserve_no, alms_payment_id)
    if key in lms_payments:
        lms_amount = lms_payments[key]
        if abs(alms_amount - lms_amount) > 0.01:  # Not matching
            mismatches.append((reserve_no, alms_payment_id, lms_amount, alms_amount))
            print(f'  {reserve_no} | PayID {alms_payment_id} | LMS: ${lms_amount:,.2f} | ALMS: ${alms_amount:,.2f} | Diff: ${alms_amount - lms_amount:+.2f}')

if not mismatches:
    print('  (None found - good!)')

# 3. Duplicate payments in ALMS
print(f'\n❌ DUPLICATE PAYMENTS (same reserve, amount, date):\n')
alms_cur.execute('''
    SELECT reserve_number, amount, payment_date, COUNT(*) as cnt
    FROM payments
    WHERE reserve_number IS NOT NULL AND amount > 0
    GROUP BY reserve_number, amount, payment_date
    HAVING COUNT(*) > 1
    ORDER BY cnt DESC
''')

dups = alms_cur.fetchall()
total_dup_records = sum(cnt - 1 for _, _, _, cnt in dups)  # Exclude first copy
if dups:
    print(f'Found {len(dups)} duplicate groups = {total_dup_records} extra records to delete\n')
    for reserve, amount, date, cnt in dups[:10]:
        print(f'  {reserve} | ${float(amount):,.2f} | {date} | {cnt} copies')
else:
    print('  (None found - good!)')

# Summary
print(f'\n' + '='*80)
print(f'\nSUMMARY - ALMS PAYMENTS TO DELETE:\n')
print(f'  Orphan (NULL reserve):        {orphan_count:6} records | ${orphan_total:>12,.2f}')
print(f'  Amount mismatches:            {len(mismatches):6} records')
print(f'  Duplicate records:            {total_dup_records:6} records')
print(f'  {"TOTAL":40} {orphan_count + len(mismatches) + total_dup_records:6} records to delete')

lms_cur.close()
lms_conn.close()
alms_cur.close()
alms_conn.close()
