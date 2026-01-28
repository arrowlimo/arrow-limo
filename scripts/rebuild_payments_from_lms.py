import pyodbc
import psycopg2

# Connect to LMS
lms_conn_str = r'Driver={Microsoft Access Driver (*.mdb, *.accdb)};DBQ=L:\limo\backups\lms.mdb;'
lms_conn = pyodbc.connect(lms_conn_str)
lms_cur = lms_conn.cursor()

# Connect to ALMS
alms_conn = psycopg2.connect(host='localhost', dbname='almsdata', user='postgres', password='***REMOVED***')
alms_cur = alms_conn.cursor()

print('=== REBUILDING ALMS PAYMENTS FROM LMS ===\n')

try:
    # Step 1: Delete all payments from ALMS
    print('Step 1: Delete all ALMS payments...')
    alms_cur.execute('SELECT COUNT(*) FROM payments')
    old_count = alms_cur.fetchone()[0]
    
    alms_cur.execute('DELETE FROM payments')
    print(f'✅ Deleted {old_count} payment records from ALMS\n')
    
    # Step 2: Import all LMS payments
    print('Step 2: Import all LMS payments...')
    lms_cur.execute('SELECT Reserve_No, PaymentID, Amount FROM Payment WHERE Reserve_No IS NOT NULL')
    
    rows = lms_cur.fetchall()
    inserted = 0
    
    for reserve_no, payment_id, amount in rows:
        reserve_no = str(reserve_no).strip()
        amount = float(amount or 0)
        payment_id = int(payment_id)
        
        # Insert into ALMS
        alms_cur.execute('''
            INSERT INTO payments (reserve_number, payment_id, amount, payment_method, is_deposited)
            VALUES (%s, %s, %s, %s, FALSE)
            ON CONFLICT DO NOTHING
        ''', (reserve_no, payment_id, amount, 'imported_from_lms'))
        
        inserted += 1
        if inserted % 5000 == 0:
            print(f'  Inserted {inserted}...')
    
    alms_conn.commit()
    print(f'✅ Inserted {inserted} clean payment records from LMS\n')
    
    # Verify
    alms_cur.execute('SELECT COUNT(*) FROM payments')
    new_count = alms_cur.fetchone()[0]
    print(f'Final count: {old_count} → {new_count}')
    print(f'\n✅ ALMS payments rebuilt from LMS source!')
    
except Exception as e:
    alms_conn.rollback()
    print(f'\n❌ Error: {e}')
finally:
    lms_cur.close()
    lms_conn.close()
    alms_cur.close()
    alms_conn.close()
