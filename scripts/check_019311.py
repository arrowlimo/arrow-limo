import psycopg2
import pyodbc

# Check PostgreSQL
pg = psycopg2.connect(host='localhost', dbname='almsdata', user='postgres', password='***REDACTED***')
cur = pg.cursor()

cur.execute('SELECT reserve_number, charter_date, total_amount_due, paid_amount, balance FROM charters WHERE reserve_number=%s', ('019311',))
ch = cur.fetchone()
print(f'PostgreSQL 019311:')
print(f'  Date: {ch[1]}')
print(f'  Due: ${float(ch[2]):.2f}')
print(f'  Paid: ${float(ch[3]):.2f}')
print(f'  Balance: ${float(ch[4]):.2f}')

cur.execute('SELECT COUNT(*), COALESCE(SUM(amount),0) FROM payments WHERE reserve_number=%s', ('019311',))
p = cur.fetchone()
print(f'  Payments in PG: {p[0]} totaling ${float(p[1]):.2f}')
print()

# Check LMS
lms = pyodbc.connect(r'DRIVER={Microsoft Access Driver (*.mdb, *.accdb)};DBQ=L:\limo\backups\lms.mdb;')
lms_cur = lms.cursor()
lms_cur.execute('SELECT Deposit, Balance, Rate FROM Reserve WHERE Reserve_No=?', ('019311',))
lms_row = lms_cur.fetchone()

if lms_row:
    print(f'LMS 019311:')
    print(f'  Deposit: ${float(lms_row[0]) if lms_row[0] else 0:.2f}')
    print(f'  Balance: ${float(lms_row[1]) if lms_row[1] else 0:.2f}')
    print(f'  Rate: ${float(lms_row[2]) if lms_row[2] else 0:.2f}')
    print()
    
    # Check LMS Payment table
    lms_cur.execute('SELECT COUNT(*), SUM(Amount) FROM Payment WHERE Reserve_No=?', ('019311',))
    lms_pay = lms_cur.fetchone()
    print(f'  Payments in LMS: {lms_pay[0] or 0} totaling ${float(lms_pay[1]) if lms_pay[1] else 0:.2f}')
    
    # Get payment details
    lms_cur.execute('SELECT PaymentID, Amount, LastUpdated FROM Payment WHERE Reserve_No=?', ('019311',))
    for row in lms_cur.fetchall():
        print(f'    Payment {row[0]}: ${float(row[1]):.2f} on {row[2]}')
else:
    print(f'LMS 019311: NOT FOUND')
