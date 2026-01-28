import pyodbc

lms_conn_str = r'Driver={Microsoft Access Driver (*.mdb, *.accdb)};DBQ=L:\limo\backups\lms.mdb;'
lms_conn = pyodbc.connect(lms_conn_str)
lms_cur = lms_conn.cursor()

print('=== LMS CHARGE & PAYMENT FOR ONE CHARTER ===\n')

# Pick a specific charter - use 019618 that we analyzed earlier
reserve_num = '019618'

# 1. Reserve record (charges)
print(f'Reserve {reserve_num}:\n')
lms_cur.execute(f'SELECT Reserve_No, PU_Date, Driver, Status FROM Reserve WHERE Reserve_No = ?', (reserve_num,))
res_row = lms_cur.fetchone()
if res_row:
    print(f'  Reserve: {res_row[0]}')
    print(f'  Pickup Date: {res_row[1]}')
    print(f'  Driver: {res_row[2]}')
    print(f'  Status: {res_row[3]}')

# 2. Check Charge table
print(f'\nCharges for this reserve:\n')
lms_cur.execute(f'SELECT ChargeID, Amount, Description FROM Charge WHERE Reserve_No = ?', (reserve_num,))
rows = lms_cur.fetchall()
total_charges = 0
for row in rows:
    amt = row[1] if row[1] else 0
    total_charges += amt
    print(f'  ChargeID {row[0]}: ${amt:,.2f} | {row[2]}')
print(f'  TOTAL CHARGES: ${total_charges:,.2f}')

# 3. Check Payment table
print(f'\nPayments for this reserve:\n')
try:
    lms_cur.execute(f'SELECT PaymentID, Amount FROM Payment WHERE Reserve_No = ?', (reserve_num,))
    rows = lms_cur.fetchall()
    total_paid = 0
    for row in rows:
        amt = row[1] if row[1] else 0
        total_paid += amt
        print(f'  PaymentID {row[0]}: ${amt:,.2f}')
    print(f'  TOTAL PAID: ${total_paid:,.2f}')
except Exception as e:
    print(f'  Error querying Payment table: {e}')

# 4. Balance
print(f'\nBalance owing: ${total_charges - total_paid:,.2f}')

lms_cur.close()
lms_conn.close()
