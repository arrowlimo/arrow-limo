import psycopg2
import pyodbc

# Connect to PostgreSQL
pg = psycopg2.connect(host='localhost', dbname='almsdata', user='postgres', password='***REDACTED***')
pg_cur = pg.cursor()

# Connect to LMS
lms = pyodbc.connect(r'DRIVER={Microsoft Access Driver (*.mdb, *.accdb)};DBQ=L:\limo\backups\lms.mdb;')
lms_cur = lms.cursor()

print("Analyzing Reserve 013932 - the biggest credit ($15,480 from 21 payments)")
print("=" * 80)
print()

# Get the 21 payments
pg_cur.execute('''
    SELECT payment_id, payment_date, payment_key, created_at
    FROM payments
    WHERE reserve_number = '013932'
    AND ABS(amount - 774.00) < 0.01
    ORDER BY payment_date
''')
payments = pg_cur.fetchall()

print(f"Found {len(payments)} $774 payments on reserve 013932:")
print()

# Check each payment in LMS
for payment_id, payment_date, payment_key, created_at in payments:
    print(f"Payment ID {payment_id}: date={payment_date}, key={payment_key}")
    
    if payment_key and payment_key.isdigit():
        # This is an LMS Payment.PaymentID
        lms_cur.execute('''
            SELECT Reserve_No, Amount, LastUpdated
            FROM Payment
            WHERE PaymentID = ?
        ''', (int(payment_key),))
        lms_row = lms_cur.fetchone()
        
        if lms_row:
            lms_reserve, lms_amount, lms_date = lms_row
            if lms_reserve != '013932':
                print(f"  ❌ LMS shows this payment belongs to reserve {lms_reserve}, NOT 013932!")
            else:
                print(f"  ✓ LMS confirms this payment is for reserve 013932")
        else:
            print(f"  ⚠ Payment key {payment_key} not found in LMS")
    else:
        print(f"  ⚠ No LMS payment key (imported from other source)")
    print()

# Check how many Waste Connections charters exist around that time
pg_cur.execute('''
    SELECT COUNT(*)
    FROM charters
    WHERE client_id = 2311
    AND ABS(total_amount_due - 774.00) < 0.01
    AND charter_date BETWEEN '2018-01-01' AND '2018-12-31'
''')
charters_2018 = pg_cur.fetchone()[0]

print(f"\nWaste Connections had {charters_2018} charters at $774 in 2018")
print(f"But reserve 013932 (June 13, 2018) has {len(payments)} payments attached")
print()
print("Expected: Each charter should have 1 payment")
print(f"Problem: {len(payments) - 1} extra payments incorrectly linked to 013932")
