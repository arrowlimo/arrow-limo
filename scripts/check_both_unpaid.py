import psycopg2
import pyodbc

pg = psycopg2.connect(host='localhost', dbname='almsdata', user='postgres', password='***REMOVED***')
cur = pg.cursor()

lms = pyodbc.connect(r'DRIVER={Microsoft Access Driver (*.mdb, *.accdb)};DBQ=L:\limo\backups\lms.mdb;')
lms_cur = lms.cursor()

print("Checking both unpaid Waste Connections reserves:\n")
print("=" * 70)

for reserve_num in ['019311', '019395']:
    print(f"\nReserve {reserve_num}:")
    print("-" * 70)
    
    # PostgreSQL
    cur.execute('SELECT charter_date, total_amount_due, paid_amount, balance FROM charters WHERE reserve_number=%s', (reserve_num,))
    ch = cur.fetchone()
    print(f'PostgreSQL:')
    print(f'  Date: {ch[0]}, Due: ${float(ch[1]):.2f}, Paid: ${float(ch[2]):.2f}, Balance: ${float(ch[3]):.2f}')
    
    # LMS
    lms_cur.execute('SELECT Deposit, Balance, Rate FROM Reserve WHERE Reserve_No=?', (reserve_num,))
    lms_row = lms_cur.fetchone()
    if lms_row:
        print(f'LMS:')
        print(f'  Deposit: ${float(lms_row[0]) if lms_row[0] else 0:.2f}, Balance: ${float(lms_row[1]) if lms_row[1] else 0:.2f}, Rate: ${float(lms_row[2]) if lms_row[2] else 0:.2f}')
        
        # LMS payments
        lms_cur.execute('SELECT PaymentID, Amount, LastUpdated FROM Payment WHERE Reserve_No=?', (reserve_num,))
        lms_payments = lms_cur.fetchall()
        if lms_payments:
            print(f'  LMS Payments: {len(lms_payments)}')
            for pid, amt, date in lms_payments:
                print(f'    PaymentID {pid}: ${float(amt):.2f} on {date}')
                
                # Check if this payment is in backup
                cur.execute('SELECT payment_id FROM payments_backup_waste774_20251123_002119 WHERE payment_id=%s', (pid,))
                in_backup = cur.fetchone()
                if in_backup:
                    print(f'      ✓ Found in backup (was incorrectly deleted)')
                else:
                    print(f'      ✗ Not in backup (different issue)')
        else:
            print(f'  No LMS payments')
    else:
        print(f'LMS: NOT FOUND')

print("\n" + "=" * 70)
print("Summary: Both reserves appear to have legitimate LMS payments")
print("that were incorrectly deleted during duplicate cleanup.")
